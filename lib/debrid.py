import copy
import requests
import requests
from threading import Lock
from concurrent.futures import ThreadPoolExecutor
from lib.api.debrid_apis.premiumize_api import Premiumize
from lib.api.debrid_apis.real_debrid_api import RealDebrid
from lib.api.debrid_apis.tor_box_api import Torbox
from lib.api.jacktook.kodi import kodilog
from lib.utils.kodi_utils import get_setting
from lib.utils.pm_utils import get_pm_link
from lib.utils.rd_utils import get_rd_link, get_rd_pack_link
from lib.utils.torbox_utils import get_torbox_link, get_torbox_pack_link
from lib.utils.torrent_utils import extract_magnet_from_url
from lib.utils.general_utils import (
    USER_AGENT_HEADER,
    get_cached,
    get_info_hash_from_magnet,
    is_pm_enabled,
    is_rd_enabled,
    is_tb_enabled,
    is_url,
    set_cached,
)


dialog_update = {"count": -1, "percent": 50}


def check_debrid_cached(query, results, mode, media_type, dialog, rescrape, episode=1):
    if not rescrape:
        if query:
            if mode == "tv" or media_type == "tv":
                cached_results = get_cached(query, params=(episode, "deb"))
            else:
                cached_results = get_cached(query, params=("deb"))

            if cached_results:
                return cached_results

    lock = Lock()
    cached_results = []
    uncached_results = []

    total = len(results)
    get_magnet_and_infohash(results, lock, dialog)

    with ThreadPoolExecutor(max_workers=total) as executor:
        if is_rd_enabled():
            rd_client = RealDebrid(encoded_token=get_setting("real_debrid_token"))
            [
                executor.submit(
                    check_rd_cached,
                    rd_client,
                    res,
                    cached_results,
                    uncached_results,
                    total,
                    dialog,
                    lock=lock,
                )
                for res in copy.deepcopy(results)
            ]
        if is_pm_enabled():
            pm_client = Premiumize(token=get_setting("premiumize_token"))
            [
                executor.submit(
                    check_pm_cached,
                    pm_client,
                    res,
                    cached_results,
                    uncached_results,
                    total,
                    dialog,
                    lock=lock,
                )
                for res in copy.deepcopy(results)
            ]
        if is_tb_enabled():
            tor_box_client = Torbox(token=get_setting("torbox_token"))
            [
                executor.submit(
                    check_torbox_cached,
                    tor_box_client,
                    res,
                    cached_results,
                    uncached_results,
                    total,
                    dialog,
                    lock=lock,
                )
                for res in copy.deepcopy(results)
            ]
        executor.shutdown(wait=True)
    dialog_update["count"] = -1
    dialog_update["percent"] = 50

    if get_setting("show_uncached"):
        cached_results.extend(uncached_results)

    if query:
        if mode == "tv" or media_type == "tv":
            set_cached(cached_results, query, params=(episode, "deb"))
        else:
            set_cached(cached_results, query, params=("deb"))

    return cached_results


def check_rd_cached(client, res, cached_results, uncached_result, total, dialog, lock):
    debrid_dialog_update(total, dialog, lock)
    info_hash = res.get("infoHash")
    if info_hash:
        res["debridType"] = "RD"
        torr_available = client.get_torrent_instant_availability(info_hash)
        if info_hash in torr_available:
            with lock:
                res["isDebrid"] = True
                cached_results.append(res)
        else:
            with lock:
                res["isDebrid"] = False
                uncached_result.append(res)


def check_pm_cached(client, res, cached_results, uncached_result, total, dialog, lock):
    debrid_dialog_update(total, dialog, lock)
    info_hash = res.get("infoHash")
    if info_hash:
        res["debridType"] = "PM"
        torr_available = client.get_torrent_instant_availability(info_hash)
        if torr_available.get("response")[0]:
            with lock:
                res["isDebrid"] = True
                cached_results.append(res)
        else:
            with lock:
                res["isDebrid"] = False
                uncached_result.append(res)


def check_torbox_cached(
    client, res, cached_results, uncached_result, total, dialog, lock
):
    debrid_dialog_update(total, dialog, lock)
    info_hash = res.get("infoHash")
    if info_hash:
        res["debridType"] = "TB"
        torr_available = client.get_torrent_instant_availability(info_hash)
        if info_hash in torr_available.get("data", {}):
            with lock:
                res["isDebrid"] = True
                cached_results.append(res)
        else:
            with lock:
                res["isDebrid"] = False
                uncached_result.append(res)


def get_magnet_and_infohash(results, lock, dialog):
    with lock:
        for count, res in enumerate(results):
            magnet = ""
            info_hash = ""
            if guid := res.get("guid"):
                if guid.startswith("magnet:?") or len(guid) == 40:
                    magnet = guid
                    info_hash = (
                        res["infoHash"].lower()
                        if res.get("infoHash")
                        else get_info_hash_from_magnet(guid).lower()
                    )
                else:
                    # For some indexers, the guid is a torrent file url
                    magnet, info_hash = get_magnet_from_uri(
                        res.get("guid"), dialog, count, results
                    )

            if not (magnet and info_hash):
                url = res.get("magnetUrl", "") or res.get("downloadUrl", "")
                if url.startswith("magnet:?"):
                    magnet = url
                    info_hash = get_info_hash_from_magnet(url).lower()
                else:
                    magnet, info_hash = get_magnet_from_uri(url, dialog, count, results)

            res["magnet"] = magnet
            res["infoHash"] = info_hash


def get_magnet_from_uri(uri, dialog, count, results):
    magnet = ""
    info_hash = ""
    dialog.update(
        0,
        "Jacktook [COLOR FFFF6B00]Debrid[/COLOR]",
        f"Extracting Magnet...{count}/{len(results)}",
    )
    if is_url(uri):
        try:
            res = requests.get(
                uri, allow_redirects=False, timeout=10, headers=USER_AGENT_HEADER
            )
            if res.status_code == 200:
                if res.is_redirect:
                    uri = res.headers.get("Location")
                    if uri.startswith("magnet:"):
                        magnet = uri
                        info_hash = get_info_hash_from_magnet(uri).lower()
                elif res.headers.get("Content-Type") == "application/octet-stream":
                    magnet = extract_magnet_from_url(uri)
        except Exception as e:
            kodilog(f"Failed to extract torrent data from: {str(e)}")
    return magnet, info_hash


def debrid_dialog_update(total, dialog, lock):
    with lock:
        dialog_update["count"] += 1
        dialog_update["percent"] += 2

        dialog.update(
            dialog_update.get("percent"),
            f"Jacktook [COLOR FFFF6B00]Debrid[/COLOR]",
            f"Checking: {dialog_update.get('count')}/{total}",
        )


def get_debrid_direct_url(info_hash, debrid_type):
    if debrid_type == "RD":
        url = get_rd_link(info_hash)
    elif debrid_type == "PM":
        url = get_pm_link(info_hash)
    elif debrid_type == "TB":
        url = get_torbox_link(info_hash)
    return url


def get_debrid_pack_direct_url(file_id, torrent_id, debrid_type):
    if debrid_type == "RD":
        url = get_rd_pack_link(file_id, torrent_id)
    elif debrid_type == "TB":
        url = get_torbox_pack_link(file_id, torrent_id)
    return url
