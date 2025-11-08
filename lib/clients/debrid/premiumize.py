import copy
from typing import Dict, List, Any, Optional
from lib.api.debrid.premiumize import Premiumize
from lib.utils.kodi.utils import get_setting, kodilog, notification
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


class PremiumizeHelper:
    def __init__(self):
        self.client = Premiumize(token=get_setting("premiumize_token"))

    def check_cached(
        self,
        results: List[TorrentStream],
        cached_results: List[TorrentStream],
        uncached_results: List[TorrentStream],
        total: int,
        dialog: Any,
        lock: Any,
    ) -> None:
        """Checks if torrents are cached in Premiumize."""
        hashes = [res.infoHash for res in results]
        torrents_info = self.client.get_torrent_instant_availability(hashes)
        cached_response = torrents_info.get("response", [])

        for index, res in enumerate(copy.deepcopy(results)):
            debrid_dialog_update("PM", total, dialog, lock)
            res.type = IndexerType.DEBRID
            res.debridType = DebridType.PM

            if index < len(cached_response) and cached_response[index] is True:
                res.isCached = True
                cached_results.append(res)
            else:
                res.isCached = False
                uncached_results.append(res)

    def get_link(self, info_hash, data) -> Optional[Dict[str, Any]]:
        """Gets a direct download link for a Premiumize torrent."""
        magnet = info_hash_to_magnet(info_hash)
        response_data = self.client.create_download_link(magnet)

        if response_data.get("status") == "error":
            kodilog(
                f"Failed to get link from Premiumize: {response_data.get('message')}"
            )
            return None

        content = response_data.get("content", [])
        if len(content) > 1:
            if data["tv_data"]:
                season = data["tv_data"].get("season", "")
                episode = data["tv_data"].get("episode", "")
                content = filter_debrid_episode(
                    content, episode_num=episode, season_num=season
                )
                if not content:
                    return
                data["url"] = content[0].get("stream_link")
                return data
            else:
                data["is_pack"] = True
                return data
        else:
            data["url"] = content[0].get("stream_link")
            return data

    def get_pack_info(self, info_hash):
        """Retrieves information about a torrent pack, including file names."""
        info = get_cached(info_hash)
        if info:
            return info

        extensions = supported_video_extensions()[:-1]
        magnet = info_hash_to_magnet(info_hash)
        response_data = self.client.create_download_link(magnet)

        if response_data.get("status") == "error":
            notification(
                f"Failed to get link from Premiumize: {response_data.get('message')}"
            )
            return None

        torrent_content = response_data.get("content", [])
        if len(torrent_content) <= 1:
            notification("No files on the current source")
            return None

        files = [
            (item.get("link"), item.get("path").rsplit("/", 1)[-1])
            for item in torrent_content
            if any(item.get("path", "").lower().endswith(ext) for ext in extensions)
            and item.get("link")
        ]

        info = {"files": files}
        set_cached(info, info_hash)
        return info
