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


class LinkNotFoundError(Exception):
    pass

class RealDebridHelper:
    def __init__(self):
        self.client = RealDebrid(token=get_setting("real_debrid_token"))

    def check_rd_cached(self, results, cached_results, uncached_results, total, dialog, lock):
        """Checks if torrents are cached in Real-Debrid."""
        torr_available = self.client.get_user_torrent_list()
        torr_available_hashes = {torr["hash"] for torr in torr_available}

        for res in copy.deepcopy(results):
            debrid_dialog_update("RD", total, dialog, lock)
            res["type"] = Debrids.RD

            with lock:
                if res.get("infoHash") in torr_available_hashes:
                    res["isCached"] = True
                    cached_results.append(res)
                else:
                    res["isCached"] = False
                    uncached_results.append(res)

        # Add uncached_results due to RD removing cached check endpoint
        cached_results.extend(uncached_results)

    def add_rd_magnet(self, info_hash, is_pack=False):
        """Adds a magnet link to Real-Debrid and returns the torrent ID."""
        try:
            torrent_info = self.client.get_available_torrent(info_hash)

            if not torrent_info:
                self.check_max_active_count()
                magnet = info_hash_to_magnet(info_hash)
                response = self.client.add_magnet_link(magnet)
                torrent_id = response.get("id")

                if not torrent_id:
                    kodilog("Failed to add magnet link to Real-Debrid")
                    return None

                torrent_info = self.client.get_torrent_info(torrent_id)

            torrent_id = torrent_info["id"]
            status = torrent_info["status"]

            if status in ["magnet_error", "error", "virus", "dead"]:
                self.client.delete_torrent(torrent_id)
                raise Exception(f"Torrent cannot be downloaded due to status: {status}")

            if status in ["queued", "downloading", "magnet_conversion"]:
                return None

            if status == "waiting_files_selection":
                self.handle_file_selection(torrent_info, is_pack)

            return torrent_id

        except ProviderException as e:
            notification(str(e))
            raise
        except Exception as e:
            notification(str(e))
            raise

    def handle_file_selection(self, torrent_info, is_pack):
        """Handles file selection for Real-Debrid torrents."""
        files = torrent_info["files"]
        extensions = supported_video_extensions()[:-1]

        video_files = [item for item in files if any(item["path"].lower().endswith(ext) for ext in extensions)]

        if video_files:
            torrents_ids = [str(i["id"]) for i in video_files] if is_pack or len(video_files) > 1 else [str(video_files[0]["id"])]
            if torrents_ids:
                kodilog(",".join(torrents_ids))
                self.client.select_files(torrent_info["id"], ",".join(torrents_ids))

    def get_rd_link(self, info_hash, data):
        """Gets a direct download link for a Real-Debrid torrent."""
        torrent_id = self.add_rd_magnet(info_hash)
        if not torrent_id:
            return None

        torr_info = self.client.get_torrent_info(torrent_id)

        if len(torr_info["links"]) > 1:
            data["is_pack"] = True
            return None

        response = self.client.create_download_link(torr_info["links"][0])
        url = response.get("download")

        if not url:
            notification("File not cached!")
            return None

        return url

    def get_rd_pack_link(self, file_id, torrent_id):
        """Gets a direct download link for a file inside a Real-Debrid torrent pack."""
        torrent_info = self.client.get_torrent_info(torrent_id)
        torrent_items = [item for item in torrent_info["files"] if item["selected"] == 1]

        index = next((index for index, item in enumerate(torrent_items) if item["id"] == file_id), None)

        if index is None:
            raise LinkNotFoundError("Requested file not found in torrent pack")

        response = self.client.create_download_link(torrent_info["links"][index])
        url = response.get("download")

        if not url:
            notification("File not cached!")
            return None

        return url

    def get_rd_pack_info(self, info_hash):
        """Retrieves information about a torrent pack, including file names."""
        info = get_cached(info_hash)
        if info:
            return info

        torrent_id = self.add_rd_magnet(info_hash, is_pack=True)
        if not torrent_id:
            return None

        torr_info = self.client.get_torrent_info(torrent_id)
        torrent_files = torr_info["files"]

        if len(torrent_files) <= 1:
            notification("Not a torrent pack")
            return None

        torr_items = [item for item in torrent_files if item["selected"] == 1]
        files = [(item["id"], item["path"].split("/", 1)[1]) for item in torr_items]

        info = {"id": torr_info["id"], "files": files}
        set_cached(info, info_hash)
        return info

    def get_rd_info(self):
        """Fetches Real-Debrid account details and displays them."""
        user = self.client.get_user()
        expiration = user["expiration"]

        try:
            expires = datetime.strptime(expiration, "%Y-%m-%dT%H:%M:%S.%fZ")
        except ValueError:
            expires = datetime(*(time.strptime(expiration, "%Y-%m-%dT%H:%M:%S.%fZ")[0:6]))

        days_remaining = (expires - datetime.today()).days
        body = [
            f"[B]Account:[/B] {user['email']}",
            f"[B]Username:[/B] {user['username']}",
            f"[B]Status:[/B] {user['type'].capitalize()}",
            f"[B]Expires:[/B] {expires}",
            f"[B]Days Remaining:[/B] {days_remaining}",
            f"[B]Fidelity Points:[/B] {user['points']}",
        ]
        dialog_text("Real-Debrid", "\n".join(body))

    def check_max_active_count(self):
        """Ensures Real-Debrid does not exceed active torrent limit."""
        active_count = self.client.get_torrent_active_count()

        if active_count["nb"] >= active_count["limit"]:
            hashes = active_count["list"]
            if hashes:
                torrents = self.client.get_user_torrent_list()
                torrent_info = next((i for i in torrents if i["hash"] == hashes[0]), None)

                if torrent_info:
                    self.client.delete_torrent(torrent_info["id"])
