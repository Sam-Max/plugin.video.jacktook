import copy
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, cast

from lib.api.debrid.base import ProviderException
from lib.api.debrid.realdebrid import RealDebrid
from lib.clients.debrid.common import (
    ensure_direct_playable_file_for_provider,
    get_file_name,
)
from lib.domain.torrent import TorrentStream
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
from lib.utils.kodi.logging import kodilog
from lib.utils.kodi.utils import (
    dialog_text,
    get_setting,
    translation,
)


class LinkNotFoundError(Exception):
    pass


class RealDebridHelper:
    # GET /torrents returns 100 entries by default and 5000 at most, so a single
    # call silently truncates larger accounts.
    CACHED_TORRENT_PAGE_SIZE: int = 1000
    CACHED_TORRENT_MAX_PAGES: int = 10

    def __init__(self) -> None:
        self.client = RealDebrid(token=str(get_setting("real_debrid_token", "")))

    def _iter_user_torrents(self) -> List[Dict[str, Any]]:
        """Collects the user's torrents across pages, stopping after the last one."""
        collected: List[Dict[str, Any]] = []
        for page in range(1, self.CACHED_TORRENT_MAX_PAGES + 1):
            batch = self.client.get_user_torrent_list(
                page=page, limit=self.CACHED_TORRENT_PAGE_SIZE
            )
            if not isinstance(batch, list) or not batch:
                break
            collected.extend(item for item in batch if isinstance(item, dict))
            if len(batch) < self.CACHED_TORRENT_PAGE_SIZE:
                break
        return collected

    def check_cached(
        self,
        results: List[TorrentStream],
        cached_results: List[TorrentStream],
        uncached_results: List[TorrentStream],
        total: int,
        dialog: object,
        lock: threading.Lock,
    ) -> None:
        # Checks if torrents are cached in Real-Debrid. GET /torrents is paginated,
        # so walk every page instead of trusting the first one only.
        # Only finished torrents are instant-available; a torrent still in
        # magnet_conversion/queued/downloading/error/... is not cached.
        torr_available_hashes = [
            t["hash"]
            for t in self._iter_user_torrents()
            if t.get("status") == "downloaded" and t.get("hash")
        ]

        for res in copy.deepcopy(results):
            debrid_dialog_update("RD", total, dialog, lock)
            res.type = IndexerType.DEBRID
            res.debridType = DebridType.RD
            with lock:
                if res.infoHash in torr_available_hashes:
                    res.isCached = True
                    cached_results.append(res)
                elif res.isCached:
                    cached_results.append(res)
                else:
                    res.isCached = False
                    uncached_results.append(res)

        if get_setting("show_uncached"):
            cached_results.extend(uncached_results)

    def add_magnet(self, info_hash: str, is_pack: bool = False):
        """Adds a magnet link to Real-Debrid and returns the torrent ID."""
        try:
            kodilog(
                f"RealDebridHelper.add_magnet: checking existing torrent for hash={str(info_hash).lower()[:12]!r}"
            )
            torrent_info = self.client.get_available_torrent(info_hash)
            if not torrent_info:
                self.check_max_active_count()
                kodilog("RealDebridHelper.add_magnet: calling Real-Debrid magnet upload API")
                response = self.client.add_magnet_link(info_hash_to_magnet(info_hash))
                torrent_id = response.get("id")
                if not torrent_id:
                    raise ProviderException("Failed to add magnet link to Real-Debrid")
                torrent_info = self.client.get_torrent_info(torrent_id)
            self._handle_torrent_status(torrent_info, is_pack)
            return torrent_info.get("id")
        except Exception as e:
            raise ProviderException(str(e)) from e

    def add_torrent_file(
        self,
        torrent_data: bytes,
        torrent_name: str = "torrent.torrent",
        is_pack: bool = False,
    ) -> Optional[str]:
        """Uploads a torrent file to Real-Debrid and returns the torrent ID."""
        try:
            self.check_max_active_count()
            kodilog(
                "RealDebridHelper.add_torrent_file: calling Real-Debrid torrent file upload API with torrent_name={!r}, size={} bytes".format(
                    torrent_name,
                    len(torrent_data or b""),
                )
            )
            response = self.client.add_torrent_file(torrent_data, torrent_name=torrent_name)
            torrent_id = response.get("id")
            if not torrent_id:
                raise ProviderException("Failed to upload torrent file to Real-Debrid")
            torrent_info = self.client.get_torrent_info(torrent_id)
            self._handle_torrent_status(torrent_info, is_pack)
            return torrent_info.get("id")
        except Exception as e:
            raise ProviderException(str(e)) from e

    def _handle_torrent_status(self, torrent_info: Dict, is_pack: bool = False) -> Optional[str]:
        """Processes torrent_info status and handles errors or file selection."""
        status = torrent_info["status"]
        torrent_id = torrent_info.get("id", "unknown")
        if status in ["magnet_error", "error", "virus", "dead"]:
            self.client.delete_torrent(torrent_info["id"])
            raise ProviderException(f"Torrent cannot be downloaded: {status}")
        elif status in ["queued", "downloading", "magnet_conversion"]:
            kodilog(
                f"RealDebridHelper: Torrent {torrent_id} is still being processed (status: {status}). It has been added to your cloud but is not ready yet."
            )
            return torrent_id
        elif status == "waiting_files_selection":
            if torrent_info.get("files"):
                self.handle_file_selection(torrent_info, is_pack)
            else:
                raise ProviderException("No files available for this torrent yet.")

    def handle_file_selection(self, torrent_info: Dict, is_pack: bool) -> None:
        """Handles file selection for Real-Debrid torrents."""
        files = torrent_info["files"]
        extensions = supported_video_extensions()[:-1]

        video_files = [
            item for item in files if any(item["path"].lower().endswith(ext) for ext in extensions)
        ]

        if video_files:
            torrents_ids = (
                [str(i["id"]) for i in video_files]
                if is_pack or len(video_files) > 1
                else [str(video_files[0]["id"])]
            )
            if torrents_ids:
                self.client.select_files(torrent_info["id"], ",".join(torrents_ids))

    def get_link(self, info_hash: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
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
        # `links` maps positionally onto the files Real-Debrid selected, so a single
        # link means one selected file - not that files[0] is that file.
        if len(links) == 1:
            selected = [f for f in files if f.get("selected") == 1]
            single_file = selected[0] if selected else {}
            ensure_direct_playable_file_for_provider(get_file_name(single_file), "Real-Debrid")
            data["url"] = create_download_for_link(links[0])
            return data

        # --- Multi-file torrent ---
        tv_data = data.get("tv_data")
        if tv_data:
            season = tv_data.get("season")
            episode = tv_data.get("episode")

            possible_matches = filter_debrid_episode(files, episode_num=episode, season_num=season)
            if not possible_matches:
                raise ProviderException("No matching episode found in torrent.")

            match_file = next((f for f in possible_matches if f.get("selected") == 1), None)
            if not match_file:
                raise ProviderException("File is not cached")

            ensure_direct_playable_file_for_provider(get_file_name(match_file), "Real-Debrid")

            selected_files = [f for f in files if f.get("selected") == 1]
            try:
                file_index = selected_files.index(match_file)
            except ValueError as exc:
                raise ProviderException("Could not map episode to Real-Debrid link.") from exc

            data["url"] = create_download_for_link(links[file_index])
            return data

        selected_files = [f for f in files if f.get("selected") == 1]
        if selected_files:
            largest_file = max(selected_files, key=lambda f: f.get("bytes", 0))
            ensure_direct_playable_file_for_provider(get_file_name(largest_file), "Real-Debrid")
            try:
                file_index = selected_files.index(largest_file)
            except ValueError:
                file_index = -1

            if 0 <= file_index < len(links):
                data["url"] = create_download_for_link(links[file_index])
                return data

        data["is_pack"] = True
        return data

    def get_pack_link(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Gets a direct download link for a file inside a Real-Debrid torrent pack."""
        pack_info = cast(Dict[str, Any], data.get("pack_info", {}) or {})
        file_position = pack_info.get("file_position", "")
        torrent_id = pack_info.get("torrent_id", "")

        torrent_info = self.client.get_torrent_info(torrent_id)
        links = torrent_info.get("links", [])

        # The cached pack index can go stale when file selection changes, so
        # validate it instead of trusting it as a list subscript.
        try:
            position = int(file_position)
        except (TypeError, ValueError) as exc:
            raise ProviderException(
                "Could not map the selected pack file to a Real-Debrid link."
            ) from exc

        if not isinstance(links, list) or not 0 <= position < len(links):
            raise ProviderException(
                "The selected pack file is no longer available in this torrent."
            )

        response = self.client.create_download_link(links[position])
        url = response.get("download")
        if not url:
            raise ProviderException("Failed to retrieve download link")

        data["url"] = url
        return data

    def get_pack_info(self, info_hash: str) -> Optional[Dict[str, Any]]:
        """Retrieves information about a torrent pack, including file names."""
        cached_info = get_cached(info_hash)
        if cached_info:
            return cast(Dict[str, Any], cached_info)

        torrent_id = self.add_magnet(info_hash, is_pack=True)
        if not torrent_id:
            return None

        torr_info = self.client.get_torrent_info(torrent_id)
        torrent_files = torr_info["files"]
        if len(torrent_files) <= 1:
            raise ProviderException("No files on the current source")

        torr_items = [item for item in torrent_files if item["selected"] == 1]
        # The documented path starts with "/"; stay safe when it does not.
        files = [(item["id"], item["path"].split("/", 1)[-1]) for item in torr_items]

        info = {"torrent_id": torr_info["id"], "files": files}
        set_cached(info, info_hash)
        return info

    def get_info(self) -> None:
        """Fetches Real-Debrid account details and displays them."""
        user = self.client.get_user()
        expiration = user["expiration"]

        # Real-Debrid may return the expiration with or without fractional
        # seconds; try both before degrading gracefully.
        expires = None
        for date_format in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
            try:
                # RD timestamps carry a trailing Z, so anchor them explicitly.
                expires = datetime.strptime(expiration, date_format).replace(tzinfo=timezone.utc)
                break
            except ValueError:
                continue

        if expires is not None:
            days_remaining: Any = (expires - datetime.now(timezone.utc)).days
            # Keep the UTC wall-clock display without the "+00:00" suffix.
            expires_display: Any = expires.replace(tzinfo=None)
        else:
            kodilog(f"RealDebridHelper.get_info: could not parse expiration {expiration!r}")
            days_remaining = "Unknown"
            expires_display = expiration

        body = [
            f"[B]Account:[/B] {user['email']}",
            f"[B]Username:[/B] {user['username']}",
            f"[B]Status:[/B] {user['type'].capitalize()}",
            f"[B]Expires:[/B] {expires_display}",
            f"[B]Days Remaining:[/B] {days_remaining}",
            f"[B]Fidelity Points:[/B] {user['points']}",
        ]
        dialog_text(translation(90659), "\n".join(body))

    def check_max_active_count(self) -> None:
        """Ensures Real-Debrid does not exceed active torrent limit."""
        active_count = self.client.get_torrent_active_count()

        if not isinstance(active_count, dict):
            kodilog("RealDebridHelper.check_max_active_count: malformed active count response")
            return

        try:
            nb = int(active_count.get("nb", 0))
            limit = int(active_count.get("limit", 0))
        except (TypeError, ValueError):
            kodilog("RealDebridHelper.check_max_active_count: malformed active count response")
            return

        # Only act at the boundary; never make torrent addition fail harder.
        if limit <= 0 or nb < limit:
            return

        torrents = self.client.get_user_torrent_list(filter="active")
        if not isinstance(torrents, list) or not torrents:
            kodilog("RealDebridHelper.check_max_active_count: no active torrents to delete")
            return

        dated_torrents: List[Tuple[datetime, Dict]] = []
        for torrent in torrents:
            if not isinstance(torrent, dict):
                continue
            added = self._parse_torrent_added(torrent)
            if added is not None:
                dated_torrents.append((added, torrent))
        if not dated_torrents:
            kodilog(
                "RealDebridHelper.check_max_active_count: active torrents "
                "have no parsable 'added' date"
            )
            return

        oldest = min(dated_torrents, key=lambda item: item[0])[1]
        torrent_id = oldest.get("id")
        if torrent_id is None:
            kodilog("RealDebridHelper.check_max_active_count: oldest active torrent has no id")
            return

        # One deletion frees one slot.
        self.client.delete_torrent(torrent_id)

    @staticmethod
    def _parse_torrent_added(torrent: Dict) -> Optional[datetime]:
        """Parses a torrent 'added' ISO-8601 date, returning None when unparsable."""
        added = torrent.get("added")
        if not added:
            return None
        for date_format in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
            try:
                return datetime.strptime(added, date_format)
            except ValueError:
                continue
        return None
