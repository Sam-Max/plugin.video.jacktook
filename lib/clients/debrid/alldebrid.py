from datetime import datetime
from typing import Dict, List, Any, Optional

from lib.api.debrid.alldebrid import AllDebrid
from lib.api.debrid.base import ProviderException
from lib.utils.kodi.utils import dialog_text, get_setting, kodilog, notification
from lib.utils.general.utils import (
    DebridType,
    IndexerType,
    debrid_dialog_update,
    filter_debrid_episode,
    info_hash_to_magnet,
    supported_video_extensions,
)
from lib.domain.torrent import TorrentStream
import threading


class AllDebridHelper:
    def __init__(self):
        self.client = AllDebrid(token=str(get_setting("alldebrid_token", "")))

    def check_cached(
        self,
        results: List[TorrentStream],
        cached_results: List[TorrentStream],
        uncached_results: List[TorrentStream],
        total: int,
        dialog: Any,
        lock: threading.Lock,
    ) -> None:
        # Checks if torrents are cached in AllDebrid.
        torr_available = self.client.get_user_torrent_list()
        magnets = (
            torr_available.get("data", {}).get("magnets")
            or torr_available.get("magnets")
            or []
        )
        torr_available_hashes = [
            m.get("hash") for m in magnets if isinstance(m, dict) and m.get("hash")
        ]

        for res in results:
            debrid_dialog_update(DebridType.AD, total, dialog, lock)
            res.type = IndexerType.DEBRID
            res.debridType = DebridType.AD
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

    def get_link(
        self, info_hash: str, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:

        result = self.client.add_magnet(info_hash_to_magnet(info_hash))
        magnet = result.get("data", {}).get("magnets", [])[0]
        if not magnet.get("ready"):
            raise ProviderException("Torrent is not yet cached!")

        torrent_id = magnet.get("id")

        # --- Get the files (and their direct links) ---
        torr_info = self.client.get_files_and_links(torrent_id)
        files = torr_info[0].get("files", [])
        if not files:
            raise ProviderException("No files found in torrent info.")

        # Flatten file list
        flat_files = self.flatten_files(files)

        # --- Single-file torrents ---
        if not data.get("tv_data"):
            # Filter only supported video files
            all_links = [
                f.get("l")
                for f in flat_files
                if any(
                    (f.get("n") or "").lower().endswith(ext)
                    for ext in supported_video_extensions()[:-1]
                )
            ]
            if not all_links:
                raise ProviderException("No cached links available!")
            data["url"] = self.create_download_for_link(all_links[0])
            return data

        # --- Multi-file torrents (TV shows) ---
        season = data["tv_data"].get("season", "")
        episode = data["tv_data"].get("episode", "")

        matched = filter_debrid_episode(
            flat_files, episode_num=episode, season_num=season
        )
        if not matched:
            raise ProviderException("No matching episode found in torrent.")

        matched_link = matched[0]["l"]
        direct_link = self.create_download_for_link(matched_link)
        data["url"] = direct_link
        return data

    def flatten_files(self, files: list) -> list:
        flat_list = []
        for f in files:
            if "e" in f:
                flat_list.extend(self.flatten_files(f["e"]))
            else:
                if "l" in f:
                    flat_list.append(f)
        return flat_list

    def get_pack_link(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Gets a direct download link for a file inside a Real-Debrid torrent pack."""

        pack_info = data.get("pack_info", {})
        link = pack_info.get("url", "")

        data["url"] = self.create_download_for_link(link)
        return data

    def get_pack_info(self, info_hash: str) -> Optional[Dict]:
        result = self.client.add_magnet(info_hash_to_magnet(info_hash))
        magnet = result.get("data", {}).get("magnets", [])[0]
        if not magnet.get("ready"):
            raise ProviderException("Torrent is not yet cached!")

        torrent_id = magnet.get("id")

        # --- Get the files (and their direct links) ---
        torr_info = self.client.get_files_and_links(torrent_id)
        files = torr_info[0].get("files", [])
        if not files:
            raise ProviderException("No files found in torrent info.")

        # Flatten file list
        flat_files = self.flatten_files(files)

        # Filter only supported video files
        files = [
            (f.get("l"), f.get("n"))
            for f in flat_files
            if any(
                (f.get("n") or "").lower().endswith(ext)
                for ext in supported_video_extensions()[:-1]
            )
        ]
        if not files:
            notification("No valid files found in torrent")
            raise

        info = {"files": files}
        return info

    def create_download_for_link(self, link: str):
        response = self.client.create_download_link(link)
        if not response:
            raise ProviderException("Failed to unlock the download link.")
        url = response.get("data", {}).get("link")
        if not url:
            raise ProviderException("File not cached!")
        return url

    def get_info(self) -> None:
        try:
            response = self.client.get_user_info()
            user = response["user"]
        except Exception as e:
            raise ProviderException("Failed to retrieve All-Debrid user info.")
        status = "Premium" if user["isPremium"] else "Not Active"
        expires = datetime.fromtimestamp(user["premiumUntil"])
        days_remaining = (expires - datetime.today()).days
        body = [
            f"[B]Account:[/B] {user['email']}",
            f"[B]Username:[/B] {user['username']}",
            f"[B]Status:[/B] {status}",
            f"[B]Expires:[/B] {expires}",
            f"[B]Days Remaining:[/B] {days_remaining}",
            f"[B]Fidelity Points:[/B] {user['fidelityPoints']}",
        ]
        dialog_text("All-Debrid", "\n".join(body))
