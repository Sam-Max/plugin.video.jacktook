import json
import os

from typing import Any, Dict, List, Optional
from lib.clients.aisubtrans.deepl import DeepLTranslator
from lib.clients.aisubtrans.opensubstremio import OpenSubtitleStremioClient
from lib.utils.kodi.utils import (
    ADDON_PROFILE_PATH,
    get_setting,
    kodilog,
)

import xbmc
import xbmcgui


class KodiJsonRpcClient:
    def json_rpc(
        self, method: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Send a JSON-RPC request to Kodi."""
        request_data = {
            "jsonrpc": "2.0",
            "method": method,
            "id": 1,
            "params": params or {},
        }
        response = json.loads(xbmc.executeJSONRPC(json.dumps(request_data)))
        if "error" in response:
            # If you want logging here, you can add a log method or pass a logger
            pass
        return response.get("result", {})


class SubtitleManager(KodiJsonRpcClient):
    def __init__(self, data: Any, notification: Any):
        self.data = data
        self.notification = notification
        self.opensub_client = OpenSubtitleStremioClient(notification)
        self.translator = DeepLTranslator(notification)

    def convert_language_iso(self, from_value: str) -> str:
        """Convert language to ISO 639-1 format."""
        return xbmc.convertLanguage(from_value, xbmc.ISO_639_1)

    def get_kodi_preferred_subtitle_language(self, iso_format: bool = False) -> str:
        """
        Get the preferred subtitle language from Kodi settings.
        Returns the language in ISO format if iso_format is True.
        """
        subtitle_language = self.json_rpc(
            "Settings.GetSettingValue", {"setting": "locale.subtitlelanguage"}
        )

        value = subtitle_language.get("value", "")
        if value in ["forced_only", "original", "default", "none"]:
            return value
        return self.convert_language_iso(value) if iso_format else value

    def get_downloaded_subtitle_paths(self, folder_path: str) -> List[str]:
        """
        Recursively find all .srt subtitle files in the given folder_path.
        """
        subtitle_files = []
        for root, _, files in os.walk(folder_path):
            for f in files:
                if f.endswith(".srt"):
                    subtitle_files.append(os.path.join(root, f))
        return subtitle_files

    def fetch_subtitles(self) -> Optional[List[str]]:
        """
        Download subtitles for the current video.
        Returns a list of subtitle file paths.
        """
        
        title = self.data.get("title")
        mode = self.data.get("mode")
        imdb_id = self.data.get("ids", {}).get("imdb_id")
        tv_data = self.data.get("tv_data", {})
        episode = tv_data.get("episode")
        season = tv_data.get("season")

        if not imdb_id:
            kodilog("No IMDb ID found for the current video")
            return

        folder_path = (
            os.path.join(ADDON_PROFILE_PATH, "subtitles", imdb_id, str(season))
            if mode == "tv"
            else os.path.join(ADDON_PROFILE_PATH, "subtitles", imdb_id)
        )

        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        subtitle_files = self.get_downloaded_subtitle_paths(folder_path)
        if subtitle_files:
            dialog = xbmcgui.Dialog()
            use_existing = dialog.yesno(
                "Subtitles Found",
                "There are already downloaded subtitles for this video.\n"
                "Do you want to use the existing subtitles?",
                yeslabel="Use Existing",
                nolabel="Download New",
            )
            if use_existing:
                return subtitle_files

        subtitles = self.opensub_client.get_subtitles(mode, imdb_id, season, episode)
        if not subtitles:
            kodilog("No subtitles found for the current video")
            return

        subtitle_paths = self.opensub_client.download_subtitles_batch(
            subtitles, imdb_id, title=title, season=season, episode=episode
        )

        if get_setting("deepl_enabled"):
            dialog = xbmcgui.Dialog()
            yes = dialog.yesno(
                "Translate Subtitles",
                "Do you want to also translate the selected subtitles?",
            )
            if yes:
                translated_subtitles_paths = (
                    self.translator.translate_multiple_subtitles(
                        subtitle_paths, imdb_id, season, episode
                    )
                )
                return translated_subtitles_paths

        return subtitle_paths


