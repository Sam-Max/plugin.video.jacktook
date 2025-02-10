import copy
from lib.clients.debrid.premiumize import Premiumize
from lib.api.jacktook.kodi import kodilog
from lib.utils.kodi_utils import get_setting, notification
from lib.utils.utils import (
    Debrids,
    Indexer,
    debrid_dialog_update,
    get_cached,
    get_random_color,
    info_hash_to_magnet,
    set_cached,
    supported_video_extensions,
)


class PremiumizeHelper:
    def __init__(self):
        self.client = Premiumize(token=get_setting("premiumize_token"))

    def check_pm_cached(self, results, cached_results, uncached_results, total, dialog, lock):
        """Checks if torrents are cached in Premiumize."""
        hashes = [res.get("infoHash") for res in results]
        torrents_info = self.client.get_torrent_instant_availability(hashes)
        cached_response = torrents_info.get("response", [])

        for index, res in enumerate(copy.deepcopy(results)):
            debrid_dialog_update("PM", total, dialog, lock)
            res["type"] = Debrids.PM

            if index < len(cached_response) and cached_response[index] is True:
                res["isCached"] = True
                cached_results.append(res)
            else:
                res["isCached"] = False
                uncached_results.append(res)

    def get_pm_link(self, info_hash):
        """Gets a direct download link for a Premiumize torrent."""
        magnet = info_hash_to_magnet(info_hash)
        response_data = self.client.create_download_link(magnet)

        if response_data.get("status") == "error":
            kodilog(f"Failed to get link from Premiumize: {response_data.get('message')}")
            return None

        content = response_data.get("content", [])
        if not content:
            return None

        selected_file = max(content, key=lambda x: x.get("size", 0))
        return selected_file.get("stream_link")

    def get_pm_pack_info(self, info_hash):
        """Retrieves information about a torrent pack, including file names."""
        info = get_cached(info_hash)
        if info:
            return info

        extensions = supported_video_extensions()[:-1]
        magnet = info_hash_to_magnet(info_hash)
        response_data = self.client.create_download_link(magnet)

        if response_data.get("status") == "error":
            notification(f"Failed to get link from Premiumize: {response_data.get('message')}")
            return None

        torrent_content = response_data.get("content", [])
        if len(torrent_content) <= 1:
            notification("Not a torrent pack")
            return None

        files = [
            (item.get("link"), item.get("path").rsplit("/", 1)[-1])
            for item in torrent_content
            if any(item.get("path", "").lower().endswith(ext) for ext in extensions) and item.get("link")
        ]

        if files:
            info = {"files": files}
            set_cached(info, info_hash)
            return info

        return None
