import copy
from typing import Dict, List, Any, Optional
from lib.api.debrid.premiumize import Premiumize
from lib.clients.debrid.common import (
    ensure_direct_playable_file_for_provider,
    get_file_name,
)
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
        token = str(get_setting("premiumize_token") or "")
        self.client = Premiumize(token=token)

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
            error_msg = response_data.get("message", "Unknown error")
            kodilog(f"Failed to get link from Premiumize: {error_msg}")
            if "not premium" in error_msg.lower():
                notification("Premiumize: Account does not have an active premium subscription", "Premiumize Error")
            elif "not logged in" in error_msg.lower():
                notification("Premiumize: Not logged in. Please authorize the addon.", "Premiumize Error")
            else:
                notification(f"Premiumize: {error_msg}", "Premiumize Error")
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
            ensure_direct_playable_file_for_provider(
                get_file_name(content[0]), "Premiumize"
            )
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
            error_msg = response_data.get("message", "Unknown error")
            kodilog(f"Failed to get pack info from Premiumize: {error_msg}")
            if "not premium" in error_msg.lower():
                notification("Premiumize: Account does not have an active premium subscription", "Premiumize Error")
            elif "not logged in" in error_msg.lower():
                notification("Premiumize: Not logged in. Please authorize the addon.", "Premiumize Error")
            else:
                notification(f"Premiumize: {error_msg}", "Premiumize Error")
            return None

        torrent_content = response_data.get("content", [])
        if len(torrent_content) <= 1:
            notification("No files on the current source")
            return None

        files = [
            (item.get("link"), get_file_name(item).rsplit("/", 1)[-1])
            for item in torrent_content
            if any(get_file_name(item).lower().endswith(ext) for ext in extensions)
            and item.get("link")
        ]

        info = {"files": files}
        set_cached(info, info_hash)
        return info
