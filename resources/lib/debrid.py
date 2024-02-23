import copy
import requests
import io

from threading import Lock
from concurrent.futures import ThreadPoolExecutor
from resources.lib.api.premiumize_api import Premiumize
from resources.lib.api.real_debrid_api import RealDebrid
from resources.lib.kodi import get_setting, log

from resources.lib.torf._torrent import Torrent
from resources.lib.utils.utils import (
    Indexer,
    get_cached,
    get_info_hash,
    info_hash_to_magnet,
    is_url,
    set_cached,
    supported_video_extensions,
)



dialog_update = {"count": -1, "percent": 50}

USER_AGENT_HEADER = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
}


def check_debrid_cached(query, results, mode, dialog, rescrape, episode=1):
    if not rescrape:
        if mode == "tv":
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

    if rd_enabled and pm_enabled:
        total = len(results) * 2
    else:
        total = len(results)

    get_magnet_and_infohash(results, lock)

    with ThreadPoolExecutor(max_workers=total) as executor:
        if rd_enabled:
            rd_client = RealDebrid(encoded_token=get_setting("real_debrid_token"))
            [
                executor.submit(
                    get_rd_link,
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
                    get_pm_link,
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
        executor.shutdown(wait=True)
    dialog_update["count"] = -1
    dialog_update["percent"] = 50

    if get_setting("show_uncached"):
        cached_results.extend(uncached_results)

    if mode == "tv":
        set_cached(cached_results, query, params=(episode, "deb"))
    else:
        set_cached(cached_results, query, params=("deb"))

    return cached_results


def get_pm_link(client, res, cached_results, uncached_result, total, dialog, lock):
    debrid_dialog_update(total, dialog, lock)
    info_hash = res.get("infoHash")
    magnet = res.get("magnet")
    try:
        if info_hash and magnet:
            torr_available = client.get_torrent_instant_availability(info_hash)
            if torr_available.get("response")[0]:
                with lock:
                    res["debridCached"] = True
                    res["debridType"] = "PM"
                    if res.get("indexer") in [Indexer.TORRENTIO, Indexer.ELHOSTED]:
                        magnet = info_hash_to_magnet(info_hash)
                response_data = client.create_download_link(magnet)
                if "error" in response_data.get("status"):
                    log(
                        f"Failed to get link from Premiumize {response_data.get('message')}"
                    )
                    return
                content = response_data.get("content")
                if len(content) > 1:
                    with lock:
                        res["debridId"] = info_hash
                else:
                    selected_file = max(content, key=lambda x: x.get("size", 0))
                    with lock:
                        res["debridLinks"] = [selected_file["stream_link"]]
                cached_results.append(res)
            else:
                with lock:
                    res["debridCached"] = False
                    uncached_result.append(res)
    except Exception as e:
        log(f"Error: {str(e)}")


def get_rd_link(client, res, cached_results, uncached_result, total, dialog, lock):
    debrid_dialog_update(total, dialog, lock)
    info_hash = res.get("infoHash")
    magnet = res.get("magnet")
    try:
        if info_hash and magnet:
            torr_available = client.get_torrent_instant_availability(info_hash)
            if info_hash in torr_available:
                with lock:
                    res["debridCached"] = True
                    res["debridType"] = "RD"
                    if res.get("indexer") in [Indexer.TORRENTIO, Indexer.ELHOSTED]:
                        magnet = info_hash_to_magnet(info_hash)
                response = client.add_magent_link(magnet)
                torrent_id = response.get("id")
                if not torrent_id:
                    log("Failed to add magnet link to Real-Debrid")
                    return
                torr_info = client.get_torrent_info(torrent_id)
                if "magnet_error" in torr_info["status"]:
                    log(f"Magnet Error: {magnet}")
                    return
                if torr_info["status"] == "waiting_files_selection":
                    files = torr_info["files"]
                    extensions = supported_video_extensions()[:-1]
                    torr_keys = [
                        str(item["id"])
                        for item in files
                        for x in extensions
                        if item["path"].lower().endswith(x)
                    ]
                    torr_keys = ",".join(torr_keys)
                    client.select_files(torr_info["id"], torr_keys)
                torr_info = client.get_torrent_info(torrent_id)
                with lock:
                    if len(torr_info["links"]) > 1:
                        res["debridId"] = torrent_id
                        res["debridLinks"] = []
                    else:
                        response = client.create_download_link(torr_info["links"][0])
                        res["debridLinks"] = [response["download"]]
                cached_results.append(res)
            else:
                with lock:
                    res["debridCached"] = False
                    uncached_result.append(res)
    except Exception as e:
        log(f"Error: {str(e)}")


def get_debrid_pack(torrent_id, debrid_type):
    links = get_cached(torrent_id)
    if links:
        return links
    try:
        links = []
        if get_setting("real_debrid_enabled") and debrid_type == "RD":
            rd_client = RealDebrid(encoded_token=get_setting("real_debrid_token"))
            torr_info = rd_client.get_torrent_info(torrent_id)
            files = torr_info["files"]
            torr_names = [item["path"] for item in files if item["selected"] == 1]
            for i, name in enumerate(torr_names):
                title = f"[B][Cached][/B]-{name.split('/', 1)[1]}"
                response = rd_client.create_download_link(torr_info["links"][i])
                links.append((response["download"], title))
        elif get_setting("premiumize_enabled") and debrid_type == "PM":
            pm_client = Premiumize(token=get_setting("premiumize_token"))
            magnet = info_hash_to_magnet(torrent_id)
            response_data = pm_client.create_download_link(magnet)
            if "error" in response_data.get("status"):
                log(
                    f"Failed to get link from Premiumize {response_data.get('message')}"
                )
                return
            extensions = supported_video_extensions()[:-1]
            for item in response_data.get("content"):
                name = item.get("path").rsplit('/', 1)[-1]
                if (
                    any(name.lower().endswith(x) for x in extensions)
                    and not item.get("link", "") == ""
                ):
                    title = f"[B][Cached][/B]-{name}"
                    links.append((item["link"], title))
        if links:
            set_cached(links, torrent_id)
            return links
    except Exception as e:
        log(f"Error: {str(e)}")
    

def get_magnet_and_infohash(results, lock):
    with lock:
        for res in results:
            guid = res.get("guid")
            if guid:
                if guid.startswith("magnet:?") or len(guid) == 40:
                    info_hash = (
                        res["infoHash"].lower()
                        if res.get("infoHash")
                        else get_info_hash(guid).lower()
                    )
                else:
                    # In some indexers, the guid is a torrent file url
                    downloadUrl = res.get("guid")
                    guid, info_hash = get_magnet_from_uri(downloadUrl)
            else:
                downloadUrl = res.get("magnetUrl") or res.get("downloadUrl")
                guid, info_hash = get_magnet_from_uri(downloadUrl)

            res["magnet"] = guid
            res["infoHash"] = info_hash


def get_magnet_from_uri(uri):
    if is_url(uri):
        res = requests.get(
            uri, allow_redirects=False, timeout=20, headers=USER_AGENT_HEADER
        )
        if res.is_redirect:
            uri = res.headers.get("Location")
            if uri.startswith("magnet:"):
                return uri, get_info_hash(uri)
        elif (
            res.status_code == 200
            and res.headers.get("Content-Type") == "application/x-bittorrent"
        ):
            torrent = Torrent.read_stream(io.BytesIO(res.content))
            return str(torrent.magnet()), torrent.magnet().infohash
        else:
            log(f"Could not get torrent data from: {uri}")
            return None, None


def debrid_dialog_update(total, dialog, lock):
    with lock:
        dialog_update["count"] += 1
        dialog_update["percent"] += 2

        dialog.update(
            dialog_update.get("percent"),
            f"Jacktook [COLOR FFFF6B00]Debrid[/COLOR]",
            f"Checking: {dialog_update.get('count')}/{total}",
        )
