from datetime import datetime
from typing import Dict, List, Any, Optional
from lib.api.debrid.easydebrid import EasyDebrid
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


class EasyDebridHelper:
    def __init__(self):
        self.client = EasyDebrid(
            token=get_setting("easydebrid_token"), user_ip=get_public_ip()
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

        cached_response = []
        if filtered_results:
            magnets = [info_hash_to_magnet(res.infoHash) for res in filtered_results]
            torrents_info = self.client.get_torrent_instant_availability(magnets)
            cached_response = torrents_info.get("cached", [])

        for res in results:
            debrid_dialog_update("ED", total, dialog, lock)
            res.type = IndexerType.DEBRID
            res.debridType = DebridType.ED

            if res in filtered_results:
                # Get index in filtered results for matching cached response
                index = filtered_results.index(res)
                is_cached = (
                    cached_response[index] if index < len(cached_response) else False
                )
                res.isCached = bool(is_cached)
                if res.isCached:
                    cached_results.append(res)
                else:
                    uncached_results.append(res)
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
            if any(item["filename"].lower().endswith(x) for x in extensions)
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
                data["url"] = torrent_files[0].get("url")
                return data
            else:
                data["is_pack"] = True
                return data
        else:
            data["url"] = torrent_files[0].get("url")
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
            notification("No files on the current source")
            return

        files = [
            (item["url"], item["filename"])
            for item in torrent_files
            if any(item["filename"].lower().endswith(x) for x in extensions)
        ]

        info = {"files": files}
        set_cached(info, info_hash)
        return info

    def get_info(self):
        user = self.client.get_user_info()
        expiration_timestamp = user["paid_until"]

        expires = datetime.fromtimestamp(expiration_timestamp)
        days_remaining = (expires - datetime.today()).days

        body = [
            f"[B]Expires:[/B] {expires}",
            f"[B]Days Remaining:[/B] {days_remaining}",
        ]
        dialog_text("Easy-Debrid", "\n".join(body))
