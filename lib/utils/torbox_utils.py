import copy
from lib.clients.debrid.torbox import Torbox
from lib.api.jacktook.kodi import kodilog
from lib.utils.kodi_utils import get_setting, notification
from lib.utils.utils import (
    Debrids,
    debrid_dialog_update,
    get_cached,
    get_public_ip,
    info_hash_to_magnet,
    set_cached,
    supported_video_extensions,
)

EXTENSIONS = supported_video_extensions()[:-1]


class TorboxException(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class TorboxHelper:
    def __init__(self):
        self.client = Torbox(token=get_setting("torbox_token"))

    def check_torbox_cached(
        self, results, cached_results, uncached_results, total, dialog, lock
    ):
        hashes = [res.get("infoHash") for res in results]
        response = self.client.get_torrent_instant_availability(hashes)
        cached_response = response.get("data", [])

        for res in copy.deepcopy(results):
            debrid_dialog_update("TB", total, dialog, lock)
            res["type"] = Debrids.TB

            with lock:
                if res.get("infoHash") in cached_response:
                    res["isCached"] = True
                    cached_results.append(res)
                else:
                    res["isCached"] = False
                    uncached_results.append(res)

    def add_torbox_torrent(self, info_hash):
        torrent_info = self.client.get_available_torrent(info_hash)
        if (
            torrent_info
            and torrent_info.get("download_finished")
            and torrent_info.get("download_present")
        ):
            return torrent_info

        magnet = info_hash_to_magnet(info_hash)
        response = self.client.add_magnet_link(magnet)

        if not response.get("success"):
            raise TorboxException(f"Failed to add magnet link to Torbox: {response}")

        if "Found Cached" in response.get("detail", ""):
            return self.client.get_available_torrent(info_hash)

    def get_torbox_link(self, info_hash):
        torrent_info = self.add_torbox_torrent(info_hash)
        if torrent_info:
            file = max(torrent_info["files"], key=lambda x: x.get("size", 0))
            response_data = self.client.create_download_link(
                torrent_info.get("id"), file.get("id"), get_public_ip()
            )
            return response_data.get("data")

    def get_torbox_pack_link(self, file_id, torrent_id):
        response = self.client.create_download_link(torrent_id, file_id)
        return response.get("data")

    def get_torbox_pack_info(self, info_hash):
        info = get_cached(info_hash)
        if info:
            return info

        torrent_info = self.add_torbox_torrent(info_hash)
        if not torrent_info:
            return None

        kodilog(torrent_info)
        info = {"id": torrent_info["id"], "files": []}
        torrent_files = torrent_info.get("files", [])

        if not torrent_files:
            notification("Not a torrent pack")
            return None

        files = [
            (id, item["name"])
            for id, item in enumerate(torrent_files)
            if any(item["short_name"].lower().endswith(ext) for ext in EXTENSIONS)
        ]

        info["files"] = files
        set_cached(info, info_hash)
        return info
