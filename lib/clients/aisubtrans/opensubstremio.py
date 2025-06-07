import requests
from typing import Callable, List, Optional, Dict, Any
from lib.clients.aisubtrans.utils import get_language_code
from lib.utils.kodi.utils import (
    ADDON_PROFILE_PATH,
    get_setting,
    kodilog,
)

import xbmcgui


class OpenSubtitleStremioClient:
    ADDON_BASE_URL = get_setting("subtitle_addon_host")

    def __init__(self, notification: Callable[[str], None]):
        self.notification = notification

    def _fetch_subtitles_data(
        self,
        mode: str,
        imdb_id: str,
        season: Optional[int] = None,
        episode: Optional[int] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        if mode == "tv":
            url = f"{self.ADDON_BASE_URL}subtitles/series/{imdb_id}:{season}:{episode}.json"
        else:
            url = f"{self.ADDON_BASE_URL}subtitles/movie/{imdb_id}.json"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                kodilog(f"OpenSubtitles Subtitles Response: {data}")
                return data.get("subtitles", [])
            else:
                self.notification(
                    f"Failed to fetch subtitles, status code {response.status_code}"
                )
                return None
        except Exception as e:
            self.notification(f"Failed to fetch subtitles: {e}")
            return None

    def _filter_subtitles_by_language(
        self, subtitles_list: List[Dict[str, Any]], lang: str
    ) -> List[Dict[str, Any]]:
        return [s for s in subtitles_list if s["lang"] == lang]

    def get_subtitles(
        self,
        mode: str,
        imdb_id: str,
        season: Optional[int] = None,
        episode: Optional[int] = None,
        lang_code: str = "eng",
    ) -> Optional[List[Dict[str, Any]]]:
        subtitles: list  = self._fetch_subtitles_data(mode, imdb_id, season, episode)
        if not subtitles:
            return

        filtered = self._filter_subtitles_by_language(subtitles, lang_code)
        if filtered:
            return filtered

        fallback = get_setting("opensub_fallback_language")
        if not fallback or fallback == "None":
            self.notification("No subtitles found for language")
            return
        
        fallback_code = get_language_code(fallback)
        filtered = self._filter_subtitles_by_language(subtitles, fallback_code)
        if not filtered:
            self.notification("No subtitles found for secondary language")
            return

        if get_setting("deepl_enabled"):
            items = [
                xbmcgui.ListItem(label=f"Subtitle No. {i}", label2=s["lang"])
                for i, s in enumerate(filtered)
            ]
            dialog = xbmcgui.Dialog()
            selected = dialog.multiselect(
                "Subtitles Selection",
                items,
                useDetails=True,
            )
            if selected is None:
                return []
            return [filtered[i] for i in selected]
        
        return filtered

    def download_subtitle(
        self,
        subtitle: Dict[str, Any],
        index: int,
        imdb_id: str,
        season: Optional[int] = None,
        episode: Optional[int] = None,
    ) -> None:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; Kodi-Subtitle-Addon/1.0)",
            "Accept": "*/*",
        }
        try:
            response = requests.get(subtitle["url"], stream=True, headers=headers, timeout=15)
            if response.status_code == 200:
                file_path = (
                    f"{ADDON_PROFILE_PATH}/{imdb_id}/{season}/subtitle.E{episode}.{index}.{subtitle['lang']}.srt"
                    if episode
                    else f"{ADDON_PROFILE_PATH}/{imdb_id}/subtitle.{index}.{subtitle['lang']}.srt"
                )

                with open(file_path, "wb") as file:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            file.write(chunk)

                return file_path
            else:
                self.notification(
                    f"Failed to download {subtitle['url']}, status code {response.status_code}"
                )
                raise Exception(f"HTTP {response.status_code}")
        except Exception as e:
            self.notification(f"Subtitle download error for {subtitle['url']}: {e}")
            raise
