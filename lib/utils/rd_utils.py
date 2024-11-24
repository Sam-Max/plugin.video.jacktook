import os
from lib.api.debrid.real_debrid_api import RealDebrid
import time
from datetime import datetime
from lib.api.jacktook.kodi import kodilog
from lib.utils.kodi_utils import (
    ADDON_PATH,
    get_setting,
    dialog_text,
    notification,
    url_for,
)
from lib.utils.utils import (
    get_cached,
    get_random_color,
    info_hash_to_magnet,
    set_cached,
    supported_video_extensions,
)
from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem


client = RealDebrid(encoded_token=get_setting("real_debrid_token"))


def add_rd_magnet(magnet, is_pack=False):
    response = client.add_magent_link(magnet)
    torrent_id = response.get("id")
    if not torrent_id:
        kodilog("Failed to add magnet link to Real-Debrid")
        return None
    torr_info = client.get_torrent_info(torrent_id)
    status = torr_info["status"]
    if status in ["magnet_error", "error", "virus", "dead"]:
        client.delete_torrent(torrent_id)
        raise Exception(f"Torrent cannot be downloaded due to status: {status}")
    elif status in ["queued", "downloading", "downloaded"]:
        return None
    elif status == "waiting_files_selection":
        files = torr_info["files"]
        extensions = supported_video_extensions()[:-1]
        video_files = [
            item
            for item in files
            for x in extensions
            if item["path"].lower().endswith(x)
        ]
        if is_pack:
            torr_keys = [str(i["id"]) for i in video_files]
            if torr_keys:
                torr_keys = ",".join(torr_keys)
                client.select_files(torr_info["id"], torr_keys)
        else:
            if video_files:
                video = max(video_files, key=lambda x: x["bytes"])
                client.select_files(torr_info["id"], video["id"])
        return torrent_id


def get_rd_link(info_hash):
    magnet = info_hash_to_magnet(info_hash)
    torrent_id = add_rd_magnet(magnet)
    if not torrent_id:
        return
    torr_info = client.get_torrent_info(torrent_id)
    if torr_info["links"]:
        response = client.create_download_link(torr_info["links"][0])
        return response.get("download")


def get_rd_pack_info(info_hash):
    info = get_cached(info_hash)
    if info:
        return info
    magnet = info_hash_to_magnet(info_hash)
    torrent_id = add_rd_magnet(magnet, is_pack=True)
    if not torrent_id:
        return
    torr_info = client.get_torrent_info(torrent_id)
    info = {}
    info["id"] = torr_info["id"]
    if len(torr_info["files"]) > 0:
        torr_names = [
            item["path"] for item in torr_info["files"] if item["selected"] == 1
        ]
        files = []
        for id, name in enumerate(torr_names):
            tracker_color = get_random_color("RD")
            title = f"[B][COLOR {tracker_color}][RD-Cached][/COLOR][/B]-{name.split('/', 1)[1]}"
            files.append((id, title))
        info["files"] = files
        set_cached(info, info_hash)
        return info
    else:
        notification("Not a torrent pack")
        return


def show_rd_pack_info(info, ids, debrid_type, tv_data, mode, plugin):
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


def get_rd_pack_link(file_id, torrent_id):
    torr_info = client.get_torrent_info(torrent_id)
    response = client.create_download_link(torr_info["links"][int(file_id)])
    return response.get("download")


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
