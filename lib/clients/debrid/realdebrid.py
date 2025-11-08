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
        # Checks if torrents are cached in Real-Debrid.
        torr_available = self.client.get_user_torrent_list()
        torr_available_hashes = [
            t.get("hash")
            for t in torr_available
            if isinstance(t, dict) and t.get("hash")
        ]

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

    def add_magnet(self, info_hash: str, is_pack: bool = False):
        """Adds a magnet link to Real-Debrid and returns the torrent ID."""
        try:
            torrent_info = self.client.get_available_torrent(info_hash)
            if not torrent_info:
                self.check_max_active_count()
                response = self.client.add_magnet_link(info_hash_to_magnet(info_hash))
                torrent_id = response.get("id")
                if not torrent_id:
                    raise ProviderException("Failed to add magnet link to Real-Debrid")
                torrent_info = self.client.get_torrent_info(torrent_id)
            self._handle_torrent_status(torrent_info, is_pack)
            return torrent_info.get("id")
        except Exception as e:
            raise ProviderException(str(e))

    def _handle_torrent_status(
        self, torrent_info: Dict, is_pack: bool = False
    ) -> Optional[str]:
        """Processes torrent_info status and handles errors or file selection."""
        status = torrent_info["status"]
        if status in ["magnet_error", "error", "virus", "dead"]:
            self.client.delete_torrent(torrent_info["id"])
            raise ProviderException(f"Torrent cannot be downloaded: {status}")
        elif status in ["queued", "downloading", "magnet_conversion"]:
            raise ProviderException("Torrent is still being processed.")
        elif status == "waiting_files_selection":
            if "files" in torrent_info and torrent_info["files"]:
                self.handle_file_selection(torrent_info, is_pack)
            else:
                raise ProviderException("No files available for this torrent yet.")

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
        torrent_info = self.client.get_torrent_info(torrent_id)
        links = torrent_info.get("links", [])
        files = torrent_info.get("files", [])

        if not links:
            raise ProviderException("No links found in torrent info.")

        def create_download_for_link(link: str) -> str:
            response = self.client.create_download_link(link)
            url = response.get("download")
            if not url:
                raise ProviderException("File not cached!")
            return url

        # --- Single-file torrent ---
        if len(links) == 1:
            data["url"] = create_download_for_link(links[0])
            return data

        # --- Multi-file torrent ---
        tv_data = data.get("tv_data")
        if tv_data:
            season = tv_data.get("season")
            episode = tv_data.get("episode")

            possible_matches = filter_debrid_episode(
                files, episode_num=episode, season_num=season
            )
            if not possible_matches:
                raise ProviderException("No matching episode found in torrent.")

            match_file = next(
                (f for f in possible_matches if f.get("selected") == 1), None
            )
            if not match_file:
                raise ValueError("File is not cached")

            selected_files = [f for f in files if f.get("selected") == 1]
            try:
                file_index = selected_files.index(match_file)
            except ValueError:
                raise ProviderException("Could not map episode to Real-Debrid link.")

            data["url"] = create_download_for_link(links[file_index])
            return data

        # --- Pack (no TV data) ---
        data["is_pack"] = True
        return data

    def get_pack_link(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Gets a direct download link for a file inside a Real-Debrid torrent pack."""

        pack_info = data.get("pack_info", {})
        file_position = pack_info.get("file_position", "")
        torrent_id = pack_info.get("torrent_id", "")

        torrent_info = self.client.get_torrent_info(torrent_id)
        links = torrent_info.get("links", [])

        response = self.client.create_download_link(links[file_position])
        url = response.get("download")
        if not url:
            raise ProviderException("Failed to retrieve download link")

        data["url"] = url
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
            raise ProviderException("No files on the current source")

        torr_items = [item for item in torrent_files if item["selected"] == 1]
        files = [(item["id"], item["path"].split("/", 1)[1]) for item in torr_items]

        info = {"torrent_id": torr_info["id"], "files": files}
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
                    (i for i in torrents if i.get("hash", "") == hashes[0]), None
                )

                if torrent_info:
                    self.client.delete_torrent(torrent_info.get("id"))
