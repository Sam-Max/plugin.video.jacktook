import copy
import requests
import requests
from threading import Lock
from concurrent.futures import ThreadPoolExecutor
from lib.api.debrid_apis.premiumize_api import Premiumize
from lib.api.debrid_apis.real_debrid_api import RealDebrid
from lib.api.debrid_apis.tor_box_api import Torbox
from lib.utils.kodi import get_setting, log, notify
from lib.utils.pm_utils import get_pm_link
from lib.utils.rd_utils import add_rd_magnet, get_rd_link
from lib.utils.torbox_utils import get_torbox_link
from lib.utils.torrent_utils import extract_magnet_from_url
from lib.utils.utils import (
    USER_AGENT_HEADER,
    Indexer,
    get_cached,
    get_info_hash_from_magnet,
    info_hash_to_magnet,
    is_url,
    set_cached,
    supported_video_extensions,
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

    rd_enabled = get_setting("real_debrid_enabled")
    pm_enabled = get_setting("premiumize_enabled")
    torbox_enabled = get_setting("torbox_enabled")

    total = len(results)
    get_magnet_and_infohash(results, lock, dialog)

    with ThreadPoolExecutor(max_workers=total) as executor:
        if rd_enabled:
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
        if pm_enabled:
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
        if torbox_enabled:
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
    magnet = res.get("magnet")
    if info_hash and magnet:
        res["debridType"] = "RD"
        torr_available = client.get_torrent_instant_availability(info_hash)
        if info_hash in torr_available:
            with lock:
                res["isDebrid"] = True
                if res.get("indexer") in [Indexer.TORRENTIO, Indexer.ELHOSTED]:
                    magnet = info_hash_to_magnet(info_hash)
                torrent_id = add_rd_magnet(client, magnet)
                if torrent_id:
                    res["torrentId"] = torrent_id
                    torr_info = client.get_torrent_info(torrent_id)
                    if len(torr_info["links"]) > 1:
                        res["isDebridPack"] = True
                    cached_results.append(res)
        else:
            with lock:
                res["isDebrid"] = False
                uncached_result.append(res)


def check_pm_cached(client, res, cached_results, uncached_result, total, dialog, lock):
    debrid_dialog_update(total, dialog, lock)
    info_hash = res.get("infoHash")
    magnet = res.get("magnet")
    extensions = supported_video_extensions()[:-1]
    if info_hash and magnet:
        res["debridType"] = "PM"
        torr_available = client.get_torrent_instant_availability(info_hash)
        if torr_available.get("response")[0]:
            with lock:
                res["isDebrid"] = True
                if res.get("indexer") in [Indexer.TORRENTIO, Indexer.ELHOSTED]:
                    magnet = info_hash_to_magnet(info_hash)
            response_data = client.create_download_link(magnet)
            if "error" in response_data.get("status"):
                log(
                    f"Failed to get link from Premiumize {response_data.get('message')}"
                )
                return
            content = response_data.get("content")
            files_names = [
                item["path"].rsplit("/", 1)[-1]
                for item in content
                for x in extensions
                if item["path"].lower().endswith(x)
            ]
            with lock:
                if len(files_names) > 1:
                    res["isDebridPack"] = True
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
    magnet = res.get("magnet")
    extensions = supported_video_extensions()[:-1]
    if info_hash and magnet:
        res["debridType"] = "TB"
        torr_available = client.get_torrent_instant_availability(info_hash)
        if info_hash in torr_available.get("data", {}):
            with lock:
                res["isDebrid"] = True
                if res.get("indexer") in [Indexer.TORRENTIO, Indexer.ELHOSTED]:
                    magnet = info_hash_to_magnet(info_hash)
            response_data = client.add_magnet_link(magnet)
            if response_data.get("detail") is False:
                notify(f"Failed to add magnet link to Torbox {response_data}")
                return
            torrent_info = client.get_available_torrent(info_hash)
            if torrent_info:
                if (
                    torrent_info["download_finished"] is True
                    and torrent_info["download_present"] is True
                ):
                    res["torrentId"] = torrent_info["id"]
                    files_names = [
                        item["name"]
                        for item in torrent_info["files"]
                        for x in extensions
                        if item["short_name"].lower().endswith(x)
                    ]
                    with lock:
                        if len(files_names) > 1:
                            res["isDebridPack"] = True
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
            log(f"Failed to extract torrent data from: {str(e)}")
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


def get_debrid_direct_url(torrent_id, info_hash, debrid_type):
    if torrent_id and debrid_type == "RD":
        rd_client = RealDebrid(encoded_token=get_setting("real_debrid_token"))
        url = get_rd_link(rd_client, torrent_id)
    elif info_hash and debrid_type == "PM":
        pm_client = Premiumize(token=get_setting("premiumize_token"))
        url = get_pm_link(pm_client, info_hash)
    elif info_hash and debrid_type == "TB":
        log("getting debrid direct url")
        torbox_client = Torbox(token=get_setting("torbox_token"))
        url = get_torbox_link(torbox_client, info_hash)
    return url
