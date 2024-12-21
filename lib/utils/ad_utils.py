from lib.clients.debrid.alldebrid import AllDebrid
from lib.api.jacktook.kodi import kodilog
from lib.clients.debrid.debrid_client import ProviderException
from lib.utils.kodi_utils import get_setting, notification
from lib.utils.utils import (
    get_cached,
    get_random_color,
    info_hash_to_magnet,
    set_cached,
    supported_video_extensions,
)

EXTENSIONS = supported_video_extensions()[:-1]

client = AllDebrid(token=get_setting("alldebrid_token"))


def add_ad_torrent(info_hash):
    kodilog("ad_utils::add_ad_torrent")
    torrent_info = client.get_available_torrent(info_hash)
    if torrent_info:
        if torrent_info["status"] == "Ready":
            return torrent_info.get("id")
        elif torrent_info["statusCode"] == 7:
            client.delete_torrent(torrent_info.get("id"))
            raise ProviderException("Not enough seeders available to parse magnet link")
    else:
        magnet = info_hash_to_magnet(info_hash)
        response = client.add_magnet_link(magnet)
        if not response.get("success", False):
            raise Exception(
                f"Failed to add magnet: {response.get('error', 'Unknown error')}"
            )
        return response["data"]["magnets"][0]["id"]


def get_ad_link(info_hash):
    torrent_id = add_ad_torrent(info_hash)
    if torrent_id:
        torrent_info = client.get_torrent_info(torrent_id)
        file = max(torrent_info["files"], key=lambda x: x.get("size", 0))
        response_data = client.create_download_link(
            torrent_info.get("id"), file.get("id")
        )
        return response_data.get("data")


def get_ad_pack_link(file_id, torrent_id):
    response = client.create_download_link(torrent_id, file_id)
    return response.get("data")


def get_ad_pack_info(info_hash):
    info = get_cached(info_hash)
    if info:
        return info
    torrent_info = add_ad_torrent(info_hash)
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
                tracker_color = get_random_color("AD")
                title = f"[B][COLOR {tracker_color}][AD-Cached][/COLOR][/B]-{name}"
                files.append((id, title))
            info["files"] = files
            set_cached(info, info_hash)
            return info
        else:
            notification("Not a torrent pack")


