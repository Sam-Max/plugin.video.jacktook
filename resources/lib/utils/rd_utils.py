from resources.lib.api.real_debrid_api import RealDebrid
from resources.lib.utils.kodi import get_setting, log
from resources.lib.utils.utils import (
    get_cached,
    info_hash_to_magnet,
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


def get_rd_link(client, infoHash):
    try:
        magnet = info_hash_to_magnet(infoHash)
        torrent_id = add_rd_magnet(client, magnet)
        if torrent_id:
            torr_info = client.get_torrent_info(torrent_id)
            response = client.create_download_link(torr_info["links"][0])
            client.delete_torrent(torrent_id)
            return response["download"]
    except Exception as e:
        log(f"Error: {str(e)}")
        if torrent_id:
            client.delete_torrent(torrent_id)


def get_rd_pack(info_hash):
    info = get_cached(info_hash)
    if info:
        return info
    try:
        info = []
        rd_client = RealDebrid(encoded_token=get_setting("real_debrid_token"))
        magnet = info_hash_to_magnet(info_hash)
        torrent_id = add_rd_magnet(rd_client, magnet)
        if torrent_id:
            torr_info = rd_client.get_torrent_info(torrent_id)
            files = torr_info["files"]
            torr_names = [item["path"] for item in files if item["selected"] == 1]
            for id, name in enumerate(torr_names):
                title = f"[B][Cached][/B]-{name.split('/', 1)[1]}"
                info.append((id, title))
        rd_client.delete_torrent(torrent_id)
        if info:
            set_cached(info, info_hash)
            return info
    except Exception as e:
        log(f"Error: {str(e)}")
        if torrent_id:
            rd_client.delete_torrent(torrent_id)


def get_rd_pack_link(id, info_hash):
    try:
        rd_client = RealDebrid(encoded_token=get_setting("real_debrid_token"))
        magnet = info_hash_to_magnet(info_hash)
        torrent_id = add_rd_magnet(rd_client, magnet)
        if torrent_id:
            torr_info = rd_client.get_torrent_info(torrent_id)
            response = rd_client.create_download_link(torr_info["links"][int(id)])
            rd_client.delete_torrent(torrent_id)
            return response["download"]
    except Exception as e:
        log(f"Error: {str(e)}")
        if torrent_id:
            rd_client.delete_torrent(torrent_id)
