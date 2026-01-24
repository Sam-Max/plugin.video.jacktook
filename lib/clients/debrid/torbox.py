import copy
from typing import Dict, List, Any, Optional
from datetime import datetime
from lib.api.debrid.torbox import Torbox
from lib.jacktook.utils import kodilog
from lib.utils.kodi.utils import get_setting, notification, dialog_text
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
        hashes = [res.infoHash for res in results]
        response = self.client.get_torrent_instant_availability(hashes)
        
        raw_data = response.get("data", [])
        cached_response = set()
        for item in raw_data:
            if isinstance(item, dict):
                if item.get('hash'):
                    cached_response.add(item.get('hash'))
            else:
                cached_response.add(item)

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

    def get_link(self, info_hash, data) -> Optional[Dict[str, Any]]:
        torrent_info = self.add_torbox_torrent(info_hash)
        if not torrent_info:
            return None

        file = max(torrent_info["files"], key=lambda x: x.get("size", 0))
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
            if any(item["short_name"].lower().endswith(ext) for ext in EXTENSIONS)
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
        dialog_text("Torbox", "\n".join(body))
