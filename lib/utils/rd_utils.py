from lib.api.real_debrid_api import RealDebrid
from lib.utils.kodi import get_setting, log
from lib.utils.utils import (
    get_cached,
    set_cached,
    supported_video_extensions,
)


def add_rd_magnet(client, magnet):
    response = client.add_magent_link(magnet)
    torrent_id = response.get("id")
    if not torrent_id:
        log("Failed to add magnet link to Real-Debrid")
        return
    torr_info = client.get_torrent_info(torrent_id)
    if "magnet_error" in torr_info["status"]:
        log(f"Magnet Error: {magnet}")
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


def get_rd_link(client, torrent_id):
    torr_info = client.get_torrent_info(torrent_id)
    links = torr_info["links"]
    if links:
        response = client.create_download_link(links[0])
        return response["download"]
    raise LinkNotFoundError("File still not available")


def get_rd_pack(torrent_id):
    info = get_cached(torrent_id)
    if info:
        return info
    rd_client = RealDebrid(encoded_token=get_setting("real_debrid_token"))
    info = []
    torr_info = rd_client.get_torrent_info(torrent_id)
    files = torr_info["files"]
    torr_names = [item["path"] for item in files if item["selected"] == 1]
    for id, name in enumerate(torr_names):
        title = f"[B][Cached][/B]-{name.split('/', 1)[1]}"
        info.append((id, title))
    if info:
        set_cached(info, torrent_id)
        return info


def get_rd_pack_link(id, torrent_id):
    rd_client = RealDebrid(encoded_token=get_setting("real_debrid_token"))
    torr_info = rd_client.get_torrent_info(torrent_id)
    response = rd_client.create_download_link(torr_info["links"][int(id)])
    return response["download"]


class LinkNotFoundError(Exception):
    pass