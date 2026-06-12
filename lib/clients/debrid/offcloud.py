import copy
from typing import Any, Dict, List, Optional

from lib.api.debrid.offcloud import Offcloud
from lib.clients.debrid.common import get_file_name, get_packed_release_message
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
from lib.utils.kodi.utils import dialog_text, get_setting, kodilog, notification

EXTENSIONS = supported_video_extensions()[:-1]


class OffcloudHelper:
    def __init__(self):
        self.client = Offcloud(token=str(get_setting("offcloud_token") or ""))

    def _get_cache_download_files(self, info_hash: str) -> List[Dict[str, Any]]:
        magnet = info_hash_to_magnet(info_hash)
        response = self.client.create_cache_download(magnet)
        return response if isinstance(response, list) else response.get("files", [])

    def _video_files(self, files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            item
            for item in files
            if any(get_file_name(item).lower().endswith(ext) for ext in EXTENSIONS)
        ]

    def check_cached(
        self,
        results: List[TorrentStream],
        cached_results: List[TorrentStream],
        uncached_results: List[TorrentStream],
        total: int,
        dialog: Any,
        lock: Any,
    ) -> None:
        filtered_results = [res for res in results if res.infoHash]
        cached_by_hash = {}

        if filtered_results:
            magnets = [info_hash_to_magnet(res.infoHash) for res in filtered_results]
            response = self.client.get_cache_info(magnets, include_files=True)
            if isinstance(response, list):
                for index, item in enumerate(response):
                    if index < len(filtered_results) and isinstance(item, dict):
                        cached_by_hash[filtered_results[index].infoHash] = bool(item.get("cached"))

        for res in copy.deepcopy(results):
            debrid_dialog_update("OC", total, dialog, lock)
            res.type = IndexerType.DEBRID
            res.debridType = DebridType.OC
            res.isCached = bool(cached_by_hash.get(res.infoHash))

            with lock:
                if res.isCached:
                    cached_results.append(res)
                else:
                    uncached_results.append(res)

    def add_cloud_download(self, info_hash: str):
        if not info_hash:
            return None
        return self.client.add_cloud_download(info_hash_to_magnet(info_hash))

    def get_cloud_downloads(self) -> List[Dict[str, Any]]:
        history = self.client.get_cloud_history()
        downloads = []

        for item in history if isinstance(history, list) else []:
            if not isinstance(item, dict) or item.get("status") != "downloaded":
                continue

            request_id = item.get("requestId", "")
            if not request_id:
                continue

            explored = self.client.explore_cloud_download(request_id, detailed=True)
            if isinstance(explored, dict) and explored.get("error") == "Bad archive":
                kodilog(
                    "Offcloud cloud listing skipped single-file transfer that cannot be explored"
                )
                continue

            files = explored.get("files", []) if isinstance(explored, dict) else []
            video_files = self._video_files(files)
            if not video_files:
                continue

            file_item = max(video_files, key=lambda file_data: file_data.get("size", 0))
            downloads.append(
                {
                    "name": get_file_name(file_item) or item.get("fileName") or "Unknown",
                    "request_id": request_id,
                    "url": file_item.get("url", ""),
                    "created_at": item.get("createdOn", ""),
                }
            )

        return downloads

    def get_link(self, info_hash, data) -> Optional[Dict[str, Any]]:
        if data.get("url"):
            return data

        files = self._video_files(self._get_cache_download_files(info_hash))
        if not files:
            notification(get_packed_release_message("Offcloud"))
            return None

        if len(files) > 1:
            if data.get("tv_data"):
                tv_data = data.get("tv_data") or {}
                files = filter_debrid_episode(
                    files,
                    episode_num=tv_data.get("episode", ""),
                    season_num=tv_data.get("season", ""),
                )
                if not files:
                    return None
            else:
                data["is_pack"] = True
                return data

        data["url"] = files[0].get("url")
        return data

    def get_pack_link(self, data) -> Optional[Dict[str, Any]]:
        pack_info = data.get("pack_info", {})
        url = pack_info.get("url", "")
        if not url:
            return None
        data["url"] = url
        return data

    def get_pack_info(self, info_hash):
        info = get_cached(info_hash)
        if info:
            return info

        files = self._video_files(self._get_cache_download_files(info_hash))
        if len(files) <= 1:
            notification("No files on the current source")
            return None

        info = {"files": [(item.get("url"), get_file_name(item)) for item in files]}
        set_cached(info, info_hash)
        return info

    def get_info(self) -> None:
        user = self.client.get_account_info()
        body = [
            f"[B]Account:[/B] {user.get('email', '')}",
            f"[B]Premium:[/B] {'Yes' if user.get('is_premium') else 'No'}",
            f"[B]Can Download:[/B] {'Yes' if user.get('can_download') else 'No'}",
        ]
        if user.get("expiration_date"):
            body.append(f"[B]Expires:[/B] {user.get('expiration_date')}")
        dialog_text("Offcloud", "\n".join(body))
