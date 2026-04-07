import copy
from typing import Dict, List, Any, Optional
from lib.api.debrid.torbox import Torbox
from lib.clients.debrid.common import get_file_name, get_packed_release_message
from lib.utils.kodi.utils import get_setting, notification, dialog_text, kodilog, translation
from lib.utils.general.utils import (
    DebridType,
    IndexerType,
    debrid_dialog_update,
    get_cached,
    get_public_ip,
    info_hash_to_magnet,
    set_cached,
    supported_video_extensions,
)
from lib.domain.torrent import TorrentStream

EXTENSIONS = supported_video_extensions()[:-1]


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
                "TorboxHelper.check_cached: checking {} hashes against TorBox cache".format(
                    len(hashes)
                )
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
                "TorboxHelper.check_cached: skipping {} results without info_hash".format(
                    missing_hashes
                )
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
            "TorboxHelper.add_torbox_torrent: checking existing torrent for hash={!r}".format(
                str(info_hash).lower()[:12]
            )
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
        
        kodilog(f"TorboxHelper: Magnet added successfully, waiting for download. Detail: {response.get('detail', 'N/A')}")
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

            file_item = max(video_files, key=lambda item: item.get("size", 0))

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
            "Torbox cloud listing: total={}, playable={}, skipped_not_dict={}, skipped_not_present={}, skipped_no_playable={}".format(
                len(torrents),
                len(downloads),
                skipped_not_dict,
                skipped_not_present,
                skipped_no_playable,
            )
        )

        return downloads

    def get_link(self, info_hash, data) -> Optional[Dict[str, Any]]:
        torrent_id = data.get("torrent_id", "")
        file_id = data.get("file_id", "")

        if torrent_id and file_id:
            response_data = self.client.create_download_link(
                torrent_id, file_id, get_public_ip()
            )
            if response_data:
                data["url"] = response_data.get("data", {})
                return data
            kodilog(
                "Torbox cloud playback failed to create link for torrent_id={!r}, file_id={!r}".format(
                    torrent_id, file_id
                )
            )
            return None

        torrent_info = self.add_torbox_torrent(info_hash)
        if not torrent_info:
            return None

        video_files = [
            item
            for item in torrent_info["files"]
            if any(get_file_name(item).lower().endswith(ext) for ext in EXTENSIONS)
        ]
        if not video_files:
            raise TorboxException(get_packed_release_message("Torbox"))

        file = max(video_files, key=lambda x: x.get("size", 0))
        response_data = self.client.create_download_link(
            torrent_info.get("id"), file.get("id"), get_public_ip()
        )
        if response_data:
            data["url"] = response_data.get("data", {})
            return data

    def get_pack_link(self, data) -> Optional[Dict[str, Any]]:
        pack_info = data.get("pack_info", {})
        file_id = pack_info.get("file_id", "")
        torrent_id = pack_info.get("torrent_id", "")

        response_data = self.client.create_download_link(torrent_id, file_id)
        if response_data:
            data["url"] = response_data.get("data", {})
            return data

    def get_pack_info(self, info_hash):
        info = get_cached(info_hash)
        if info:
            return info

        torrent_info = self.add_torbox_torrent(info_hash)
        if not torrent_info:
            return None

        info = {
            "id": torrent_info["id"],
            "torrent_id": torrent_info["id"],
            "files": [],
        }
        torrent_files = torrent_info.get("files", [])

        if not torrent_files:
            notification("No files on the current source")
            return None

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
        plans = {
            0: "Free",
            1: "Essential",
            2: "Pro",
            3: "Standard"
        }
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
