import copy
from lib.clients.debrid.torbox import Torbox
from lib.api.jacktook.kodi import kodilog
from lib.utils.kodi_utils import get_setting, notification
from lib.utils.utils import (
    Debrids,
    Indexer,
    debrid_dialog_update,
    get_cached,
    get_public_ip,
    info_hash_to_magnet,
    set_cached,
    supported_video_extensions,
)

EXTENSIONS = supported_video_extensions()[:-1]

client = Torbox(token=get_setting("torbox_token"))


def check_torbox_cached(
    results, cached_results, uncached_results, total, dialog, lock
):
    hashes = [res.get("infoHash") for res in results]
    response = client.get_torrent_instant_availability(hashes)
    cached_response = response.get("data", [])

    for res in copy.deepcopy(results):
        debrid_dialog_update("TB", total, dialog, lock)

        res["type"] = Debrids.TB
        if res.get("infoHash") in cached_response:
            with lock:
                res["isCached"] = True
                cached_results.append(res)
        else:
            with lock:
                res["isCached"] = False
                uncached_results.append(res)


def add_torbox_torrent(info_hash):
    torrent_info = client.get_available_torrent(info_hash)
    if torrent_info:
        if (
            torrent_info["download_finished"] is True
            and torrent_info["download_present"] is True
        ):
            return torrent_info
    else:
        magnet = info_hash_to_magnet(info_hash)
        response = client.add_magnet_link(magnet)
        if response.get("success") is False:
            raise TorboxException(f"Failed to add magnet link to Torbox {response}")
        if "Found Cached" in response.get("detail", ""):
            torrent_info = client.get_available_torrent(info_hash)
            if torrent_info:
                return torrent_info


def get_torbox_link(info_hash):
    torrent_info = add_torbox_torrent(info_hash)
    if torrent_info:
        file = max(torrent_info["files"], key=lambda x: x.get("size", 0))
        response_data = client.create_download_link(
            torrent_info.get("id"), file.get("id"), get_public_ip()
        )
        return response_data.get("data")


def get_torbox_pack_link(file_id, torrent_id):
    response = client.create_download_link(torrent_id, file_id)
    return response.get("data")


def get_torbox_pack_info(info_hash):
    info = get_cached(info_hash)
    if info:
        return info
    torrent_info = add_torbox_torrent(info_hash)
    info = {}
    if torrent_info:
        kodilog(torrent_info)
        info["id"] = torrent_info["id"]
        torrent_files = torrent_info["files"]
        if len(torrent_files) > 0:
            files_names = [
                item["name"]
                for item in torrent_files
                for x in EXTENSIONS
                if item["short_name"].lower().endswith(x)
            ]
            files = []
            for id, name in enumerate(files_names):
                files.append((id, name))
            info["files"] = files
            set_cached(info, info_hash)
            return info
        else:
            notification("Not a torrent pack")


class TorboxException(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)
