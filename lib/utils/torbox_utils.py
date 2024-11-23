import os
from lib.api.debrid_apis.tor_box_api import Torbox
from lib.api.jacktook.kodi import kodilog
from lib.utils.kodi_utils import ADDON_PATH, get_setting, notification, url_for
from lib.utils.utils import (
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


def get_torbox_pack_info(info_hash):
    info = get_cached(info_hash)
    if info:
        return info
    add_torbox_torrent(info_hash)
    torr_info = client.get_available_torrent(info_hash)
    info = {}
    if torr_info:
        info["id"] = torr_info["id"]
        if len(torr_info["files"]) > 0:
            files_names = [
                item["name"]
                for item in torr_info["files"]
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


def get_torbox_link(info_hash):
    kodilog("torbox::get_torbox_link")
    add_torbox_torrent(info_hash)
    torr_info = client.get_available_torrent(info_hash)
    if torr_info:
        file = max(torr_info["files"], key=lambda x: x.get("size", 0))
        response_data = client.create_download_link(torr_info.get("id"), file.get("id"))
        return response_data.get("data")


def add_torbox_torrent(info_hash):
    kodilog("torbox::add_torbox_torrent")
    magnet = info_hash_to_magnet(info_hash)
    response_data = client.add_magnet_link(magnet)
    if response_data.get("success") is False:
        raise TorboxException(f"Failed to add magnet link to Torbox {response_data}")


def get_torbox_pack_link(file_id, torrent_id):
    kodilog("torbox_utils::get_torbox_pack_link")
    response = client.create_download_link(torrent_id, file_id)
    kodilog(response)
    return response.get("data")


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
