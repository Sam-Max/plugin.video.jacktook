import copy
import threading
import time
from datetime import datetime
from typing import Any, List, Dict, Optional
from lib.api.debrid.base import ProviderException
from lib.api.debrid.realdebrid import RealDebrid
from lib.utils.kodi.utils import (
    get_setting,
    dialog_text,
    kodilog,
    notification,
)
from lib.utils.general.utils import (
    DebridType,
    IndexerType,
    debrid_dialog_update,
    filter_debrid_episode,
    get_cached,
    info_hash_to_magnet,
    set_cached,
    supported_video_extensions,
)
from lib.domain.torrent import TorrentStream


class LinkNotFoundError(Exception):
    pass


class RealDebridHelper:
    def __init__(self) -> None:
        self.client = RealDebrid(token=str(get_setting("real_debrid_token", "")))

    def check_cached(
        self,
        results: List[TorrentStream],
        cached_results: List[TorrentStream],
        uncached_results: List[TorrentStream],
        total: int,
        dialog: object,
        lock: threading.Lock,
    ) -> None:
        """Checks if torrents are cached in Real-Debrid."""
        torr_available = self.client.get_user_torrent_list()
        torr_available_hashes = {torr["hash"] for torr in torr_available}

        for res in copy.deepcopy(results):
            debrid_dialog_update("RD", total, dialog, lock)
            res.type = IndexerType.DEBRID
            res.debridType = DebridType.RD
            with lock:
                if res.infoHash in torr_available_hashes:
                    res.isCached = True
                    cached_results.append(res)
                elif res.isCached == True:
                    cached_results.append(res)
                else:
                    res.isCached = False
                    uncached_results.append(res)

        if get_setting("show_uncached"):
            cached_results.extend(uncached_results)

    def _handle_torrent_status(
        self, torrent_info: Dict, is_pack: bool = False
    ) -> Optional[str]:
        """Processes torrent_info status and handles errors or file selection."""
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

    def add_magnet(self, info_hash: str, is_pack: bool = False) -> Optional[str]:
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

            return self._handle_torrent_status(torrent_info, is_pack)

        except ProviderException as e:
            notification(str(e))
            raise
        except Exception as e:
            notification(str(e))
            raise

    def handle_file_selection(self, torrent_info: Dict, is_pack: bool) -> None:
        """Handles file selection for Real-Debrid torrents."""
        files = torrent_info["files"]
        extensions = supported_video_extensions()[:-1]

        video_files = [
            item
            for item in files
            if any(item["path"].lower().endswith(ext) for ext in extensions)
        ]

        if video_files:
            torrents_ids = (
                [str(i["id"]) for i in video_files]
                if is_pack or len(video_files) > 1
                else [str(video_files[0]["id"])]
            )
            if torrents_ids:
                self.client.select_files(torrent_info["id"], ",".join(torrents_ids))

    def get_link(
        self, info_hash: str, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Gets a direct download link for a Real-Debrid torrent."""
        torrent_id = self.add_magnet(info_hash)
        if not torrent_id:
            return None

        torr_info = self.client.get_torrent_info(torrent_id)
        links = torr_info.get("links")
        if not links:
            notification("No files available for this torrent.")
            return None

         # --- Single-file torrent ---
        if len(links) == 1:
            response = self.client.create_download_link(links[0])
            download_url = response.get("download")
            if download_url:
                data["url"] = download_url
                return data
            else:
                notification("File not cached!")
                return None

        # --- Multi-file torrent (TV episode or pack) ---
        if data.get("tv_data"):
            season = data["tv_data"].get("season", "")
            episode = data["tv_data"].get("episode", "")
            matched = filter_debrid_episode(
                torr_info["files"], episode_num=episode, season_num=season
            )
            if not matched:
                notification("No matching episode found in torrent.")
                return None
            
            file_match = matched[0]
            file_index = next(
                (i for i, f in enumerate(torr_info["files"]) if f["id"] == file_match["id"]),
                None,
            )
            if file_index is None:
                kodilog("Could not map episode to Real-Debrid link.")
                return None

            response = self.client.create_download_link(links[file_index])
            download_url = response.get("download")
            if download_url:
                data["url"] = download_url
                return data
            else:
                notification("File not cached!")
                return None
        else:
            data["is_pack"] = True
            return data


    def get_pack_link(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Gets a direct download link for a file inside a Real-Debrid torrent pack."""

        pack_info = data.get("pack_info", {})
        file_id = pack_info.get("file_id", "")
        torrent_id = pack_info.get("torrent_id", "")

        torrent_info = self.client.get_torrent_info(torrent_id)
        torrent_items = [
            item for item in torrent_info["files"] if item["selected"] == 1
        ]

        index = next(
            (
                index
                for index, item in enumerate(torrent_items)
                if item["id"] == file_id
            ),
            None,
        )

        if index is None:
            raise LinkNotFoundError("Requested file not found in torrent pack")

        response = self.client.create_download_link(torrent_info["links"][index])
        url = response.get("download")
        if not url:
            notification("File not cached!")
            return None

        data["url"] = url
        data["pack_info"] = {
            "file_id": file_id,
            "torrent_id": torrent_id,
        }
        return data

    def get_pack_info(self, info_hash: str) -> Optional[Dict]:
        """Retrieves information about a torrent pack, including file names."""
        info = get_cached(info_hash)
        if info:
            return info

        torrent_id = self.add_magnet(info_hash, is_pack=True)
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

    def get_info(self) -> None:
        """Fetches Real-Debrid account details and displays them."""
        user = self.client.get_user()
        expiration = user["expiration"]

        try:
            expires = datetime.strptime(expiration, "%Y-%m-%dT%H:%M:%S.%fZ")
        except ValueError:
            expires = datetime(
                *(time.strptime(expiration, "%Y-%m-%dT%H:%M:%S.%fZ")[0:6])
            )

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

    def check_max_active_count(self) -> None:
        """Ensures Real-Debrid does not exceed active torrent limit."""
        active_count = self.client.get_torrent_active_count()

        if active_count["nb"] >= active_count["limit"]:
            hashes = active_count["list"]
            if hashes:
                torrents = self.client.get_user_torrent_list()
                torrent_info = next(
                    (i for i in torrents if i["hash"] == hashes[0]), None
                )

                if torrent_info:
                    self.client.delete_torrent(torrent_info["id"])
