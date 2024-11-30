import copy
import os
from lib.clients.debrid.torbox import Torbox
from lib.api.jacktook.kodi import kodilog
from lib.utils.kodi_utils import ADDON_PATH, get_setting, notification, url_for
from lib.utils.utils import (
    debrid_dialog_update,
    get_cached,
    get_random_color,
    info_hash_to_magnet,
    set_cached,
    supported_video_extensions,
)
from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem

EXTENSIONS = supported_video_extensions()[:-1]

client = Torbox(token=get_setting("torbox_token"))


def check_torbox_cached(results, cached_results, uncached_results, total, dialog, lock):
    kodilog("debrid::check_torbox_cached")
    hashes = [res.get("infoHash") for res in results]
    response = client.get_torrent_instant_availability(hashes)
    for res in copy.deepcopy(results):
        debrid_dialog_update("TB", total, dialog, lock)
        info_hash = res.get("infoHash")
        if info_hash:
            res["debridType"] = "TB"
            if info_hash in response.get("data", []):
                with lock:
                    res["isDebrid"] = True
                    cached_results.append(res)
            else:
                with lock:
                    res["isDebrid"] = False
                    uncached_results.append(res)


def add_torbox_torrent(info_hash):
    kodilog("torbox_utils::add_torbox_torrent")
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
    kodilog("torbox::get_torbox_link")
    torrent_info = add_torbox_torrent(info_hash)
    if torrent_info:
        file = max(torrent_info["files"], key=lambda x: x.get("size", 0))
        response_data = client.create_download_link(
            torrent_info.get("id"), file.get("id")
        )
        return response_data.get("data")


def get_torbox_pack_link(file_id, torrent_id):
    kodilog("torbox_utils::get_torbox_pack_link")
    response = client.create_download_link(torrent_id, file_id)
    return response.get("data")


def get_torbox_pack_info(info_hash):
    info = get_cached(info_hash)
    if info:
        return info
    torrent_info = add_torbox_torrent(info_hash)
    info = {}
    if torrent_info:
        info["id"] = torrent_info["id"]
        if len(torrent_info["files"]) > 0:
            files_names = [
                item["name"]
                for item in torrent_info["files"]
                for x in EXTENSIONS
                if item["short_name"].lower().endswith(x)
            ]
            files = []
            for id, name in enumerate(files_names):
                tracker_color = get_random_color("TB")
                title = f"[B][COLOR {tracker_color}][TB-Cached][/COLOR][/B]-{name}"
                files.append((id, title))
            info["files"] = files
            set_cached(info, info_hash)
            return info
        else:
            notification("Not a torrent pack")


def show_tb_pack_info(info, ids, debrid_type, tv_data, mode, plugin):
    for file_id, title in info["files"]:
        list_item = ListItem(label=title)
        list_item.setArt(
            {"icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png")}
        )
        addDirectoryItem(
            plugin.handle,
            url_for(
                name="play_from_pack",
                title=title,
                mode=mode,
                data={
                    "ids": ids,
                    "tv_data": tv_data,
                    "debrid_info": {
                        "file_id": file_id,
                        "torrent_id": info["id"],
                        "debrid_type": debrid_type,
                        "is_debrid_pack": True,
                    },
                },
            ),
            list_item,
            isFolder=False,
        )


class TorboxException(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)
