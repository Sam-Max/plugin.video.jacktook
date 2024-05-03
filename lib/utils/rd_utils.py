from lib.api.debrid_apis.real_debrid_api import RealDebrid
from lib.api.jacktook.kodi import kodilog
from lib.utils.kodi import get_setting
from lib.utils.utils import (
    get_cached,
    info_hash_to_magnet,
    set_cached,
    supported_video_extensions,
)

client = RealDebrid(encoded_token=get_setting("real_debrid_token"))


def add_rd_magnet(magnet):
    response = client.add_magent_link(magnet)
    torrent_id = response.get("id")
    if not torrent_id:
        kodilog("Failed to add magnet link to Real-Debrid")
        return
    torr_info = client.get_torrent_info(torrent_id)
    if "magnet_error" in torr_info["status"]:
        kodilog(f"Magnet Error: {magnet}")
        client.delete_torrent(torrent_id)
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
    return torrent_id


def get_rd_link(info_hash):
    magnet = info_hash_to_magnet(info_hash)
    torrent_id = add_rd_magnet(magnet)
    torr_info = client.get_torrent_info(torrent_id)
    links = torr_info["links"]
    if links:
        response = client.create_download_link(links[0])
        return response["download"]
    raise LinkNotFoundError("Error: File not available")


def get_rd_pack_info(info_hash):
    info = get_cached(info_hash)
    if info:
        return info
    magnet = info_hash_to_magnet(info_hash)
    torrent_id = add_rd_magnet(magnet)
    torr_info = client.get_torrent_info(torrent_id)
    info = {}
    info["id"] = torr_info["id"]
    torr_names = [item["path"] for item in torr_info["files"] if item["selected"] == 1]
    files = []
    for id, name in enumerate(torr_names):
        title = f"[B][Cached][/B]-{name.split('/', 1)[1]}"
        files.append((id, title))
    if info:
        info["files"] = files
        set_cached(info, info_hash)
        return info


def get_rd_pack_link(file_id, torrent_id):
    torr_info = client.get_torrent_info(torrent_id)
    response = client.create_download_link(torr_info["links"][int(file_id)])
    return response["download"]


class LinkNotFoundError(Exception):
    pass
