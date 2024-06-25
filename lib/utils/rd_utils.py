from lib.api.debrid_apis.real_debrid_api import RealDebrid
import time
from datetime import datetime
from lib.api.jacktook.kodi import kodilog
from lib.utils.kodi_utils import get_setting, dialog_text, notification
from lib.utils.general_utils import (
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
    if torrent_id:
        torr_info = client.get_torrent_info(torrent_id)
        if torr_info["links"]:
            response = client.create_download_link(torr_info["links"][0])
            return response["download"]


def get_rd_pack_info(info_hash):
    info = get_cached(info_hash)
    if info:
        return info
    magnet = info_hash_to_magnet(info_hash)
    torrent_id = add_rd_magnet(magnet)
    torr_info = client.get_torrent_info(torrent_id)
    info = {}
    info["id"] = torr_info["id"]
    if len(torr_info["files"]) > 0:
        torr_names = [item["path"] for item in torr_info["files"] if item["selected"] == 1]
        files = []
        for id, name in enumerate(torr_names):
            title = f"[B][Cached][/B]-{name.split('/', 1)[1]}"
            files.append((id, title))
        info["files"] = files
        set_cached(info, info_hash)
        return info
    else:
        notification("Not a torrent pack")
        return


def get_rd_pack_link(file_id, torrent_id):
    torr_info = client.get_torrent_info(torrent_id)
    response = client.create_download_link(torr_info["links"][int(file_id)])
    return response["download"]


def get_rd_info():
    user = client.get_user()
    expiration = user["expiration"]
    kodilog(expiration)
    try:
        expires = datetime.strptime(expiration, "%Y-%m-%dT%H:%M:%S.%fZ")
    except:
        expires = datetime(*(time.strptime(expiration, "%Y-%m-%dT%H:%M:%S.%fZ")[0:6]))
    days_remaining = (expires - datetime.today()).days
    body = []
    append = body.append
    append("[B]Account:[/B] %s" % user["email"])
    append("[B]Username:[/B] %s" % user["username"])
    append("[B]Status:[/B] %s" % user["type"].capitalize())
    append("[B]Expires:[/B] %s" % expires)
    append("[B]Days Remaining:[/B] %s" % days_remaining)
    append("[B]Fidelity Points:[/B] %s" % user["points"])
    dialog_text("Real-Debrid", "\n".join(body))


class LinkNotFoundError(Exception):
    pass
