import copy
from lib.api.jacktook.kodi import kodilog
from lib.clients.debrid.easydebrid import EasyDebrid
from lib.utils.kodi_utils import get_setting, notification
from lib.utils.utils import (
    Debrids,
    Indexer,
    debrid_dialog_update,
    get_cached,
    get_public_ip,
    get_random_color,
    info_hash_to_magnet,
    set_cached,
    supported_video_extensions,
)


client = EasyDebrid(token=get_setting("easydebrid_token"), user_ip=get_public_ip())


def check_ed_cached(results, cached_results, uncached_results, total, dialog, lock):
    kodilog("ed_utils::check_ed_cached")
    magnets = [info_hash_to_magnet(res["infoHash"]) for res in results]
    torrents_info = client.get_torrent_instant_availability(magnets)
    cached_response = torrents_info.get("cached", [])
    for e, res in enumerate(copy.deepcopy(results)):
        if res["indexer"] == Indexer.JACKGRAM:
             continue
        debrid_dialog_update("ED", total, dialog, lock)
        res["type"] = Debrids.ED
        if cached_response[e] is True:
            res["isCached"] = True
            cached_results.append(res)
        else:
            res["isCached"] = False
            uncached_results.append(res)


def get_ed_link(info_hash):
    kodilog("ed_utils::get_ed_link")
    magnet = info_hash_to_magnet(info_hash)
    response_data = client.create_download_link(magnet)
    files = response_data.get("files", [])
    if files:
        file = max(files, key=lambda x: x.get("size", 0))
        return file["url"]


def get_ed_pack_info(info_hash):
    info = get_cached(info_hash)
    if info:
        return info
    extensions = supported_video_extensions()[:-1]
    magnet = info_hash_to_magnet(info_hash)
    response_data = client.create_download_link(magnet)
    info = {}
    torrent_files = response_data.get("files", [])
    if len(torrent_files) > 1:
        files = []
        for item in torrent_files:
            name = item["filename"]
            if any(name.lower().endswith(x) for x in extensions):
                files.append((item["url"], name))
        info["files"] = files
        if info:
            set_cached(info, info_hash)
            return info
    else:
        notification("Not a torrent pack")
        return

