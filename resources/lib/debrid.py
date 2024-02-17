import requests
import io

from threading import Lock
from concurrent.futures import ThreadPoolExecutor
from resources.lib.kodi import get_setting, log

from resources.lib.torf._torrent import Torrent
from resources.lib.utils.utils import (
    Indexer,
    add_item,
    get_cached,
    get_info_hash,
    info_hash_to_magnet,
    is_url,
    set_cached,
    set_video_item,
    supported_video_extensions,
)

from xbmcgui import ListItem
from xbmcplugin import endOfDirectory

dialog_update = {"count": -1, "percent": 50}

USER_AGENT_HEADER = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
}


def check_debrid_cached(query, results, mode, client, dialog, episode=1):
    if mode == "tv":
        cached_results = get_cached(query, params=(episode, "deb"))
    else:
        cached_results = get_cached(query, params=("deb"))
    if cached_results:
        return cached_results

    lock = Lock()
    cached_results = []
    uncached_results = []
    total_results = len(results)
    with ThreadPoolExecutor(max_workers=total_results) as executor:
        [
            executor.submit(
                get_rd_link,
                client,
                res,
                total_results,
                dialog,
                cached_results,
                uncached_results,
                lock=lock,
            )
            for res in results
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


def get_rd_link(client, res, total, dialog, cached_results, uncached_result, lock):
    try:
        magnet, infoHash = get_magnet_and_infohash(res, lock)
        debrid_dialog_update(total, dialog, lock)

        if infoHash and magnet:
            torr_available = client.get_torrent_instant_availability(infoHash)
            if infoHash in torr_available:
                with lock:
                    res["rdCached"] = True
                    cached_results.append(res)
                    if res.get("indexer") == Indexer.TORRENTIO:
                        magnet = info_hash_to_magnet(infoHash)
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
                        res["rdId"] = torrent_id
                        res["rdLinks"] = torr_info["links"]
                    else:
                        response = client.create_download_link(torr_info["links"][0])
                        res["rdLinks"] = [response["download"]]
            else:
                with lock:
                    res["rdCached"] = False
                    uncached_result.append(res)
    except Exception as e:
        log(f"Error: {str(e)}")


def get_rd_pack(torrent_id, func, client, plugin):
    cached = False
    try:
        links = get_cached(torrent_id)
        if links:
            cached = True
        else:
            torr_info = client.get_torrent_info(torrent_id)
            files = torr_info["files"]
            torr_names = [item["path"] for item in files if item["selected"] == 1]
            links = []
            for i, name in enumerate(torr_names):
                title = f"[B][Cached][/B]-{name.split('/', 1)[1]}"
                response = client.create_download_link(torr_info["links"][i])
                links.append((response["download"], title))
            if links:
                cached = True
                set_cached(links, torrent_id)

        if cached:
            for link, title in links:
                list_item = ListItem(label=f"{title}")
                set_video_item(list_item, title, "", "")
                add_item(
                    list_item,
                    link,
                    magnet="",
                    id="",
                    title=title,
                    func=func,
                    plugin=plugin,
                )
            endOfDirectory(plugin.handle)
        
    except Exception as e:
        log(f"Error: {str(e)}")


def get_magnet_and_infohash(res, lock):
    with lock:
        guid = res.get("guid")
        if guid:
            if guid.startswith("magnet:?") or len(guid) == 40:
                info_hash = (
                    res["infoHash"].lower()
                    if res.get("infoHash")
                    else get_info_hash(guid).lower()
                )
                return guid, info_hash
            else:
                # In some indexers, the guid is a torrent file url
                downloadUrl = res.get("guid")
                return get_magnet_from_uri(downloadUrl)
        else:
            downloadUrl = res.get("magnetUrl") or res.get("downloadUrl")
            return get_magnet_from_uri(downloadUrl)


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
