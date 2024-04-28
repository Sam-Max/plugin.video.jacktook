from lib.api.debrid_apis.tor_box_api import Torbox
from lib.utils.kodi import get_setting
from lib.utils.utils import get_cached, set_cached


def get_torbox_link(client, info_hash):
    torr_info = client.get_available_torrent(info_hash)
    file = max(torr_info["files"], key=lambda x: x.get("size", 0))
    response_data = client.create_download_link(torr_info.get("id"), file.get("id"))
    return response_data.get("data")


def get_torbox_pack_info(info_hash):
    info = get_cached(info_hash)
    if info:
        return info
    client = Torbox(token=get_setting("torbox_token"))
    info = []
    torr_info = client.get_available_torrent(info_hash)
    torr_names = [item["name"] for item in torr_info["files"]]
    for id, name in enumerate(torr_names):
        title = f"[B][Cached][/B]-{name}"
        info.append((id, title))
    if info:
        set_cached(info, info_hash)
        return info


def get_tb_pack_link(file_id, torrent_id):
    client = Torbox(token=get_setting("torbox_token"))
    response = client.create_download_link(torrent_id, file_id)
    return response.get("data")
