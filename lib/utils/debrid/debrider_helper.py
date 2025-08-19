from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from lib.api.debrid.debrider import Debrider
from lib.utils.kodi.utils import dialog_text, get_setting, notification
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
from lib.domain.torrent import TorrentStream


class DebriderHelper:
    def __init__(self):
        self.client = Debrider(
            token=get_setting("debrider_token"), user_ip=get_public_ip()
        )

    def check_cached(
        self,
        results: List[TorrentStream],
        cached_results: List[TorrentStream],
        uncached_results: List[TorrentStream],
        total: int,
        dialog: Any,
        lock: Any,
    ) -> None:
        # Filter results that have an infoHash
        filtered_results = [res for res in results if res.infoHash]

        cached_lookup = {}
        if filtered_results:
            magnets = [info_hash_to_magnet(res.infoHash) for res in filtered_results]
            torrents_info = self.client.get_torrent_instant_availability(magnets)
            cached_list = torrents_info.get("result", [])

            cached_lookup = {
                res.infoHash: availability
                for res, availability in zip(filtered_results, cached_list)
            }

        for res in results:
            debrid_dialog_update(DebridType.DB, total, dialog, lock)

            res.type = IndexerType.DEBRID
            res.debridType = DebridType.DB

            availability = cached_lookup.get(res.infoHash)
            if availability and availability.get("cached", False):
                res.isCached = True
                cached_results.append(res)
            else:
                res.isCached = False
                uncached_results.append(res)

    def get_link(self, info_hash, data) -> Optional[Dict[str, Any]]:
        magnet = info_hash_to_magnet(info_hash)
        response_data = self.client.create_download_link(magnet)
        torrent_files = response_data.get("files", [])

        extensions = supported_video_extensions()[:-1]
        torrent_files = [
            item
            for item in torrent_files
            if any(item["name"].lower().endswith(x) for x in extensions)
        ]

        if not torrent_files:
            notification("No valid files found in torrent")
            return

        if len(torrent_files) > 1:
            if data["tv_data"]:
                season = data["tv_data"].get("season", "")
                episode = data["tv_data"].get("episode", "")
                torrent_files = filter_debrid_episode(
                    torrent_files, episode_num=episode, season_num=season
                )
                if not torrent_files:
                    return
                data["url"] = torrent_files[0].get("download_link")
                return data
            else:
                data["is_pack"] = True
                return data
        else:
            data["url"] = torrent_files[0].get("download_link")
            return data

    def get_pack_info(self, info_hash):
        info = get_cached(info_hash)
        if info:
            return info

        extensions = supported_video_extensions()[:-1]
        magnet = info_hash_to_magnet(info_hash)
        response_data = self.client.create_download_link(magnet)
        torrent_files = response_data.get("files", [])

        if len(torrent_files) <= 1:
            notification("Not a torrent pack")
            return

        files = [
            (item["download_link"], item["name"])
            for item in torrent_files
            if any(item["name"].lower().endswith(x) for x in extensions)
        ]

        info = {"files": files}
        set_cached(info, info_hash)
        return info

    def add_magnet(self, info_hash: str) -> Optional[str]:
        try:
            magnet = info_hash_to_magnet(info_hash)
            response = self.client.add_torrent_file(magnet)
            if (
                not response.get("message", "")
                or "task added successfully" not in response.get("message", "").lower()
            ):
                notification(f"Failed to add magnet link to Debrider {response}")
                return
        except Exception as e:
            notification(str(e))
            raise

    def get_info(self):
        user = self.client.get_user_info()
        subscription = user.get("subscription")

        if not subscription or subscription.get("status") != "active":
            dialog_text(DebridType.DB, "No active subscription found.")
            return

        plan = subscription.get("plan", {})
        plan_name = plan.get("name", "Unknown")
        plan_price = plan.get("price", "N/A")
        plan_currency = plan.get("currency", "")
        start_date_str = subscription.get("start_date")
        end_date_str = subscription.get("end_date")

        # Convert start/end dates from ISO strings to datetime
        start_date = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
        if end_date_str:
            end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
            days_remaining = (end_date - datetime.now(timezone.utc)).days
            expires_text = end_date.strftime("%Y-%m-%d %H:%M:%S UTC")
        else:
            days_remaining = "Unlimited"
            expires_text = "No expiration"

        body = [
            f"[B]Plan:[/B] {plan_name} ({plan_price} {plan_currency})",
            f"[B]Status:[/B] {subscription.get('status')}",
            f"[B]Start Date:[/B] {start_date.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"[B]Expires:[/B] {expires_text}",
            f"[B]Days Remaining:[/B] {days_remaining}",
        ]

        dialog_text(DebridType.DB, "\n".join(body))
