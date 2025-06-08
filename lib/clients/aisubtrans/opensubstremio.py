import requests
from typing import Callable, List, Optional, Dict, Any
from lib.clients.aisubtrans.utils import language_code_to_name
from lib.utils.general.utils import USER_AGENT_HEADER
from lib.utils.kodi.utils import (
    ADDON_PROFILE_PATH,
    get_setting,
    kodilog,
)
import xbmcgui


class OpenSubtitleStremioClient:
    def __init__(self, notification: Callable[[str], None]):
        self.notification = notification
        self.base_url = get_setting("stremio_sub_addon_host")

    def _build_url(
        self, mode: str, imdb_id: str, season: Optional[int], episode: Optional[int]
    ) -> str:
        if mode == "tv":
            return f"{self.base_url}subtitles/series/{imdb_id}:{season}:{episode}.json"
        return f"{self.base_url}subtitles/movie/{imdb_id}.json"

    def _fetch_subtitles_data(
        self,
        mode: str,
        imdb_id: str,
        season: Optional[int] = None,
        episode: Optional[int] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        url = self._build_url(mode, imdb_id, season, episode)
        try:
            response = requests.get(url)
            if response.status_code != 200:
                self.notification(
                    f"Failed to fetch subtitles, status code {response.status_code}"
                )
                return None
            data = response.json()
            kodilog(f"OpenSubtitles Subtitles Response: {data}")
            return data.get("subtitles", [])
        except Exception as e:
            self.notification(f"Failed to fetch subtitles: {e}")
            return None

    def _filter_subtitles_by_language(
        self, subtitles_list: List[Dict[str, Any]], lang: str
    ) -> List[Dict[str, Any]]:
        return [s for s in subtitles_list if s.get("lang") == lang]

    def get_subtitles(
        self,
        mode: str,
        imdb_id: str,
        season: Optional[int] = None,
        episode: Optional[int] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        subtitles = self._fetch_subtitles_data(mode, imdb_id, season, episode)
        if not subtitles:
            return None

        items = [
            xbmcgui.ListItem(
                label=f"Subtitle No. {i}", label2=language_code_to_name(s["lang"])
            )
            for i, s in enumerate(subtitles)
        ]

        dialog = xbmcgui.Dialog()
        selected_indices =  dialog.multiselect(
            "Select Subtitle to Download",
            items,
            useDetails=True,
        )
    
        if selected_indices is None:
            return []

        return [subtitles[i] for i in selected_indices]

    def download_subtitles_batch(
        self,
        subtitles: List[Dict[str, Any]],
        imdb_id: str,
        season: Optional[int] = None,
        episode: Optional[int] = None,
    ) -> List[str]:
        file_paths = []
        for idx, subtitle in enumerate(subtitles):
            try:
                file_path = self.download_subtitle(
                    subtitle, idx, imdb_id, season, episode
                )
                if file_path:
                    file_paths.append(file_path)
            except Exception:
                # Notification already handled in download_subtitle
                continue
        return file_paths

    def download_subtitle(
        self,
        subtitle: Dict[str, Any],
        index: int,
        imdb_id: str,
        season: Optional[int] = None,
        episode: Optional[int] = None,
    ) -> Optional[str]:
        url = subtitle.get("url")
        lang = subtitle.get("lang")

        if season is not None and episode is not None:
            file_path = f"{ADDON_PROFILE_PATH}{imdb_id}/{season}/subtitle.E{episode}.{index}.{lang}.srt"
        else:
            file_path = f"{ADDON_PROFILE_PATH}{imdb_id}/subtitle.{index}.{lang}.srt"

        try:
            response = requests.get(url, stream=True, headers=USER_AGENT_HEADER, timeout=15)
            if response.status_code != 200:
                self.notification(
                    f"Failed to download {url}, status code {response.status_code}"
                )
                raise Exception(f"HTTP {response.status_code}")
            with open(file_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file.write(chunk)
            return file_path
        except Exception as e:
            self.notification(f"Subtitle download error for {url}: {e}")
            raise
