from lib.api.debrid_apis.tor_box_api import Torbox
from lib.utils.kodi_utils import get_setting, notification
from lib.utils.general_utils import (
    get_cached,
    info_hash_to_magnet,
    set_cached,
    supported_video_extensions,
)


EXTENSIONS = supported_video_extensions()[:-1]

client = Torbox(token=get_setting("torbox_token"))


def add_torbox_torrent(info_hash):
    magnet = info_hash_to_magnet(info_hash)
    response_data = client.add_magnet_link(magnet)
    if response_data.get("detail") is False:
        notification(f"Failed to add magnet link to Torbox {response_data}")


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
                title = f"[B][Cached][/B]-{name}"
                files.append((id, title))
            info["files"] = files
            set_cached(info, info_hash)
            return info
        else:
            notification("Not a torrent pack")


def get_torbox_link(info_hash):
    add_torbox_torrent(info_hash)
    torr_info = client.get_available_torrent(info_hash)
    file = max(torr_info["files"], key=lambda x: x.get("size", 0))
    response_data = client.create_download_link(torr_info.get("id"), file.get("id"))
    return response_data.get("data")


def get_torbox_pack_link(file_id, torrent_id):
    response = client.create_download_link(torrent_id, file_id)
    return response.get("data")
