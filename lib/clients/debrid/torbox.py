import copy
from contextlib import suppress
from datetime import timedelta
from hashlib import sha256
from typing import Any, Dict, List, Optional

from xbmc import Monitor
from xbmcgui import DialogProgress

from lib.api.debrid.torbox import Torbox
from lib.clients.debrid.common import get_file_name, get_packed_release_message
from lib.db.cached import cache
from lib.domain.torrent import TorrentStream
from lib.utils.general.utils import (
    DebridType,
    IndexerType,
    debrid_dialog_update,
    filter_debrid_episode,
    get_cached,
    get_public_ip,
    info_hash_to_magnet,
    set_cached,
    supported_video_extensions,
)
from lib.utils.kodi.settings import is_cache_enabled
from lib.utils.kodi.utils import (
    dialog_text,
    get_setting,
    kodilog,
    notification,
    translation,
)
from lib.utils.player.timing import PlaybackTiming

EXTENSIONS = supported_video_extensions()[:-1]
METADATA_CACHE_TTL = timedelta(minutes=60)


def get_torbox_public_ip():
    """Use a short, provider-specific IP cache for automatic CDN routing."""
    return get_public_ip(cache_key="torbox_public_ip", cache_ttl=timedelta(minutes=1))


class TorboxException(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class TorboxHelper:
    def __init__(self):
        self.client = Torbox(token=get_setting("torbox_token"))

    def check_cached(
        self,
        results: List[TorrentStream],
        cached_results: List[TorrentStream],
        uncached_results: List[TorrentStream],
        total: int,
        dialog: Any,
        lock: Any,
    ) -> None:
        hashes = [res.infoHash for res in results if res.infoHash]
        cached_response = set()

        if hashes:
            kodilog(
                f"TorboxHelper.check_cached: checking {len(hashes)} hashes against TorBox cache"
            )
            response = self.client.get_torrent_instant_availability(hashes)
            raw_data = response.get("data", [])
            for item in raw_data:
                if isinstance(item, dict):
                    if item.get("hash"):
                        cached_response.add(item.get("hash"))
                else:
                    cached_response.add(item)

        missing_hashes = len(results) - len(hashes)
        if missing_hashes:
            kodilog(
                f"TorboxHelper.check_cached: skipping {missing_hashes} results without info_hash"
            )

        for res in copy.deepcopy(results):
            debrid_dialog_update("TB", total, dialog, lock)
            res.type = IndexerType.DEBRID
            res.debridType = DebridType.TB

            with lock:
                if res.infoHash in cached_response:
                    res.isCached = True
                    cached_results.append(res)
                else:
                    res.isCached = False
                    uncached_results.append(res)

    def add_torbox_torrent(self, info_hash):
        kodilog(
            f"TorboxHelper.add_torbox_torrent: checking existing torrent for hash={str(info_hash).lower()[:12]!r}"
        )
        torrent_info = self.client.get_available_torrent(info_hash)
        if (
            torrent_info
            and torrent_info.get("download_finished")
            and torrent_info.get("download_present")
        ):
            return torrent_info

        magnet = info_hash_to_magnet(info_hash)
        kodilog("TorboxHelper.add_torbox_torrent: calling TorBox magnet upload API")
        response = self.client.add_magnet_link(magnet)

        if not response.get("success"):
            raise TorboxException(f"Failed to add magnet link to Torbox: {response}")

        if "Found Cached" in response.get("detail", ""):
            return self.client.get_available_torrent(info_hash)

        kodilog(
            f"TorboxHelper: Magnet added successfully, waiting for download. Detail: {response.get('detail', 'N/A')}"
        )
        return response

    def add_torrent_file(self, torrent_data: bytes, torrent_name: str = "torrent.torrent"):
        kodilog(
            "TorboxHelper.add_torrent_file: calling TorBox torrent file upload API with torrent_name={!r}, size={} bytes".format(
                torrent_name,
                len(torrent_data or b""),
            )
        )
        response = self.client.add_torrent_file(torrent_data, torrent_name=torrent_name)

        if not response.get("success"):
            raise TorboxException(f"Failed to add torrent file to Torbox: {response}")

        data = response.get("data", {}) or {}
        torrent_hash = data.get("hash", "")
        if torrent_hash:
            torrent_info = self.client.get_available_torrent(torrent_hash)
            if torrent_info:
                return torrent_info
        return data

    def get_cloud_downloads(self) -> List[Dict[str, Any]]:
        response = self.client.get_user_torrent_list()
        torrents = response.get("data", {}) or []
        downloads = []
        skipped_not_dict = 0
        skipped_not_present = 0
        skipped_no_playable = 0

        for torrent in torrents:
            if not isinstance(torrent, dict):
                skipped_not_dict += 1
                continue

            if not torrent.get("download_present"):
                skipped_not_present += 1
                continue

            files = torrent.get("files", []) or []
            video_files = [
                item
                for item in files
                if any(get_file_name(item).lower().endswith(ext) for ext in EXTENSIONS)
            ]
            if not video_files:
                skipped_no_playable += 1
                continue

            for file_item in video_files:
                downloads.append(
                    {
                        "name": file_item.get("name") or torrent.get("name") or "Unknown",
                        "torrent_id": torrent.get("id"),
                        "file_id": file_item.get("id"),
                        "info_hash": torrent.get("hash", ""),
                        "created_at": torrent.get("created_at", ""),
                        "updated_at": torrent.get("updated_at", ""),
                    }
                )

        kodilog(
            f"Torbox cloud listing: total={len(torrents)}, playable={len(downloads)}, skipped_not_dict={skipped_not_dict}, skipped_not_present={skipped_not_present}, skipped_no_playable={skipped_no_playable}"
        )

        return downloads

    def _metadata_cache_key(self, info_hash):
        token = getattr(self.client, "token", None)
        if (
            not isinstance(token, str)
            or not token
            or not isinstance(info_hash, str)
            or not info_hash
        ):
            return None
        if not is_cache_enabled():
            return None
        account_scope = sha256(token.encode("utf-8")).hexdigest()
        return f"torbox_ready_metadata|{account_scope}|{info_hash.lower()}"

    @staticmethod
    def _ready_metadata(info):
        return (
            isinstance(info, dict)
            and info.get("id") not in (None, "")
            and info.get("download_finished") is True
            and info.get("download_present") is True
            and isinstance(info.get("files"), list)
            and bool(info["files"])
            and all(
                isinstance(item, dict)
                and item.get("id") not in (None, "")
                and isinstance(get_file_name(item), str)
                and bool(get_file_name(item))
                for item in info["files"]
            )
        )

    def _remember_metadata(self, info_hash, info):
        key = self._metadata_cache_key(info_hash)
        if key and self._ready_metadata(info):
            with suppress(Exception):
                cache.set(key, copy.deepcopy(info), METADATA_CACHE_TTL)

    def _invalidate_metadata(self, info_hash):
        key = self._metadata_cache_key(info_hash)
        if key:
            with suppress(Exception):
                cache.delete(key)

    def _get_torrent_metadata(self, info_hash, use_cache=True) -> Optional[Dict[str, Any]]:
        self._metadata_from_cache = False
        key = self._metadata_cache_key(info_hash)
        if use_cache and key:
            with suppress(Exception):
                cached = cache.get(key)
                if self._ready_metadata(cached):
                    self._metadata_from_cache = True
                    return copy.deepcopy(cached)

        torrent_info = self.add_torbox_torrent(info_hash)
        if torrent_info and torrent_info.get("id") not in (None, "") and torrent_info.get("files"):
            self._remember_metadata(info_hash, torrent_info)
            return torrent_info
        if not info_hash:
            return None

        progress = DialogProgress()
        monitor = Monitor()
        try:
            progress.create("Torbox", translation(90554))
            for attempt in range(3):
                if progress.iscanceled() or monitor.abortRequested():
                    return None
                progress.update(attempt * 100 // 3)
                if monitor.waitForAbort(1) or progress.iscanceled():
                    return None
                torrent_info = self.client.get_available_torrent(info_hash)
                if progress.iscanceled() or monitor.abortRequested():
                    return None
                if (
                    torrent_info
                    and torrent_info.get("id") not in (None, "")
                    and torrent_info.get("files")
                ):
                    self._remember_metadata(info_hash, torrent_info)
                    return torrent_info
        finally:
            progress.close()

        notification("Torbox is still processing this torrent. Please try again in a moment.")
        return None

    def get_link(self, info_hash, data) -> Optional[Dict[str, Any]]:
        return self._resolve_link(info_hash, data, use_cache=True)

    def _resolve_link(self, info_hash, data, use_cache):
        timing = PlaybackTiming("torbox")
        torrent_id = data.get("torrent_id", "")
        file_id = data.get("file_id", "")

        if torrent_id and file_id:
            response_data = self._create_timed_download_link(torrent_id, file_id, timing)
            if response_data:
                data["url"] = response_data.get("data", {})
                return data
            kodilog(
                f"Torbox cloud playback failed to create link for torrent_id={torrent_id!r}, file_id={file_id!r}"
            )
            return None

        with timing.stage("torbox_metadata"):
            torrent_info = self._get_torrent_metadata(info_hash, use_cache=use_cache)
        from_cache = self._metadata_from_cache
        timing.mark("torbox_metadata_cache", outcome="hit" if from_cache else "miss")
        if not torrent_info:
            return None

        torrent_files = torrent_info["files"]
        video_files = [
            item
            for item in torrent_files
            if any(get_file_name(item).lower().endswith(ext) for ext in EXTENSIONS)
        ]
        if not video_files:
            raise TorboxException(get_packed_release_message("Torbox"))

        tv_data = data.get("tv_data")
        if tv_data:
            video_files = filter_debrid_episode(
                video_files,
                episode_num=tv_data.get("episode"),
                season_num=tv_data.get("season"),
                exact_match=True,
                extra_episode_nums=(tv_data.get("anime_episode"),),
            )
            if not video_files:
                raise TorboxException("No matching episode found in torrent.")

        file = max(video_files, key=lambda x: x.get("size", 0))
        response_data = self._create_timed_download_link(
            torrent_info.get("id"), file.get("id"), timing
        )
        if response_data:
            data["url"] = response_data.get("data", {})
            return data
        self._invalidate_metadata(info_hash)
        if from_cache and use_cache:
            return self._resolve_link(info_hash, data, use_cache=False)

    def get_pack_link(self, data) -> Optional[Dict[str, Any]]:
        pack_info = data.get("pack_info", {})
        file_id = pack_info.get("file_id", "")
        torrent_id = pack_info.get("torrent_id", "")

        response_data = self._create_timed_download_link(
            torrent_id, file_id, PlaybackTiming("torbox")
        )
        if response_data:
            data["url"] = response_data.get("data", {})
            return data

    def _create_timed_download_link(self, torrent_id, file_id, timing):
        with timing.stage("torbox_public_ip"):
            user_ip = get_torbox_public_ip()
        with timing.stage("torbox_download_link"):
            return self.client.create_download_link(torrent_id, file_id, user_ip)

    def get_pack_info(self, info_hash):
        info = get_cached(info_hash)
        if info:
            return info

        torrent_info = self._get_torrent_metadata(info_hash)
        if not torrent_info:
            return None

        info = {
            "id": torrent_info["id"],
            "torrent_id": torrent_info["id"],
            "files": [],
        }
        torrent_files = torrent_info["files"]

        files = [
            (item.get("id"), item["name"])
            for id, item in enumerate(torrent_files)
            if any(get_file_name(item).lower().endswith(ext) for ext in EXTENSIONS)
        ]

        info["files"] = files
        set_cached(info, info_hash)
        return info

    def get_info(self) -> None:
        """Fetches Torbox account details and displays them."""
        response = self.client.get_user()
        if not response.get("success"):
            notification("Failed to fetch Torbox user info")
            return

        user = response.get("data", {})
        customer_email = user.get("customer_email", "")
        plan = user.get("plan", 0)

        # Plan mapping (based on general knowledge of Torbox plans, might need adjustment)
        plans = {0: "Free", 1: "Essential", 2: "Pro", 3: "Standard"}
        plan_name = plans.get(plan, f"Plan {plan}")

        body = [
            f"[B]Account:[/B] {customer_email}",
            f"[B]Plan:[/B] {plan_name}",
            f"[B]User ID:[/B] {user.get('auth_id')}",
            f"[B]Cooldown Until:[/B] {user.get('cooldown_until') or 'None'}",
        ]

        days = self.client.days_remaining()
        if days is not None:
            body.append(f"[B]Days Remaining:[/B] {days}")
        dialog_text(translation(90656), "\n".join(body))
