import copy
import time
from datetime import datetime
from lib.api.jacktook.kodi import kodilog
from lib.clients.debrid.debrid_client import ProviderException
from lib.clients.debrid.realdebrid import RealDebrid
from lib.utils.kodi_utils import (
    get_setting,
    dialog_text,
    notification,
)
from lib.utils.utils import (
    Debrids,
    debrid_dialog_update,
    get_cached,
    info_hash_to_magnet,
    set_cached,
    supported_video_extensions,
)


def check_rd_cached(results, cached_results, uncached_results, total, dialog, lock):
    client = RealDebrid(token=get_setting("real_debrid_token"))
    torr_available = client.get_user_torrent_list()
    torr_available_hashes = [torr["hash"] for torr in torr_available]

    for res in copy.deepcopy(results):
        debrid_dialog_update("RD", total, dialog, lock)

        res["type"] = Debrids.RD
        if res.get("infoHash") in torr_available_hashes:
            res["isCached"] = True
            cached_results.append(res)
        else:
            res["isCached"] = False
            uncached_results.append(res)

    # Add uncached_results cause of RD removed cached check endpoint
    cached_results.extend(uncached_results)


def add_rd_magnet(client, info_hash, is_pack=False):
    try:
        torrent_info = client.get_available_torrent(info_hash)
        if not torrent_info:
            check_max_active_count(client)

            magnet = info_hash_to_magnet(info_hash)
            response = client.add_magnet_link(magnet)
            torrent_id = response.get("id")

            if not torrent_id:
                kodilog("Failed to add magnet link to Real-Debrid")
                return

            torrent_info = client.get_torrent_info(torrent_id)

        torrent_id = torrent_info["id"]
        status = torrent_info["status"]

        if status in ["magnet_error", "error", "virus", "dead"]:
            client.delete_torrent(torrent_id)
            raise Exception(f"Torrent cannot be downloaded due to status: {status}")

        if status in ["queued", "downloading", "magnet_conversion"]:
            return

        if status == "waiting_files_selection":
            handle_file_selection(client, torrent_info, is_pack)

        return torrent_id

    except ProviderException as e:
        notification(str(e))
        raise
    except Exception as e:
        notification(str(e))
        raise


def handle_file_selection(client, torrent_info, is_pack):
    files = torrent_info["files"]
    extensions = supported_video_extensions()[:-1]

    video_files = [
        item
        for item in files
        for ext in extensions
        if item["path"].lower().endswith(ext)
    ]

    if video_files:
        if is_pack:
            torrents_ids = [str(i["id"]) for i in video_files]
            if torrents_ids:
                torrents_ids = ",".join(torrents_ids)
                client.select_files(torrent_info["id"], torrents_ids)
        else:
            video = max(video_files, key=lambda x: x["bytes"])
            client.select_files(torrent_info["id"], video["id"])


def get_rd_link(info_hash):
    client = RealDebrid(token=get_setting("real_debrid_token"))
    torrent_id = add_rd_magnet(client, info_hash)
    if not torrent_id:
        return
    torr_info = client.get_torrent_info(torrent_id)
    if torr_info["links"]:
        response = client.create_download_link(torr_info["links"][0])
        url = response.get("download")
        if not url:
            notification("File not cached!")
            return
        return url


def get_rd_pack_link(file_id, torrent_id):
    client = RealDebrid(token=get_setting("real_debrid_token"))
    torr_info = client.get_torrent_info(torrent_id)
    index = next(
        (
            index
            for index, item in enumerate(torr_info["files"])
            if item["id"] == file_id
        ),
        None,
    )
    response = client.create_download_link(torr_info["links"][index - 1])
    url = response.get("download")
    if not url:
        notification("File not cached!")
        return
    return url


def get_rd_pack_info(info_hash):
    info = get_cached(info_hash)
    if info:
        return info
    client = RealDebrid(token=get_setting("real_debrid_token"))
    torrent_id = add_rd_magnet(client, info_hash, is_pack=True)
    if not torrent_id:
        return
    torr_info = client.get_torrent_info(torrent_id)
    info = {}
    torrent_files = torr_info["files"]
    if len(torrent_files) <= 1:
        notification("Not a torrent pack")
        return
    torr_items = [item for item in torrent_files if item["selected"] == 1]
    files = []
    for item in torr_items:
        title = item["path"].split("/", 1)[1]
        files.append((item["id"], title))
    info["id"] = torr_info["id"]
    info["files"] = files
    set_cached(info, info_hash)
    return info


def get_rd_info():
    client = RealDebrid(token=get_setting("real_debrid_token"))
    user = client.get_user()
    expiration = user["expiration"]
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


def check_max_active_count(client):
    active_count = client.get_torrent_active_count()
    if active_count["nb"] >= active_count["limit"]:
        hashes = active_count["list"]
        if hashes:
            torrents = client.get_user_torrent_list()
            torrent_info = [i for i in torrents if i["hash"] == hashes[0]]
            torrent_id = torrent_info[0]["id"]
            client.delete_torrent(torrent_id)  # delete one to open a slot


class LinkNotFoundError(Exception):
    pass
