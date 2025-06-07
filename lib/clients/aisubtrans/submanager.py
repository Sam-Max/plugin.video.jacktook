import json
import os

from typing import Any, Dict, List, Optional, Union

from lib.clients.aisubtrans.deepl import DeepLTranslator
from lib.clients.aisubtrans.opensubstremio import OpenSubtitleStremioClient
from lib.clients.aisubtrans.utils import get_language_code
from lib.utils.kodi.utils import (
    ADDON_PROFILE_PATH,
    get_setting,
    kodilog,
)

import xbmc


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
    def __init__(self, kodi_player: Any, notification: Any):
        self.player = kodi_player
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

        value = subtitle_language.get("value")
        if value in ["forced_only", "original", "default", "none"]:
            return value
        return self.convert_language_iso(value) if iso_format else value

    def fetch_subtitles(self) -> Optional[List[str]]:
        """
        Download subtitles for the current video.
        Returns a list of subtitle file paths.
        """

        primary_language = get_setting("opensub_language")
        if primary_language == "None":
            kodilog("No primary language set for subtitles")
            return

        lang_code = get_language_code(primary_language)
        kodilog(f"Language: {lang_code}")

        data = self.player.data
        mode = data.get("mode")
        imdb_id = data.get("imdb_id")
        episode = data.get("episode")
        season = data.get("season")

        if not imdb_id:
            kodilog("No IMDb ID found for the current video")
            return

        folder_path = (
            f"{ADDON_PROFILE_PATH}/{imdb_id}/{season}"
            if mode == "tv"
            else f"{ADDON_PROFILE_PATH}/{imdb_id}"
        )

        if os.path.exists(folder_path):
            kodilog("Loading subtitles from local folder...")
            return [
                os.path.join(folder_path, f)
                for f in os.listdir(folder_path)
                if f.endswith(".srt")
            ]

        subtitles = self.opensub_client.get_subtitles(
            mode, imdb_id, season, episode, lang_code
        )
        if not subtitles:
            kodilog("No subtitles found for the current video")
            return

        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        for count, sub in enumerate(subtitles):
            file_path = self.opensub_client.download_subtitle(
                sub, count, imdb_id, season=season, episode=episode
            )
            sub["url"] = file_path

        if get_setting("deepl_enabled"):
            return self.translator.process_subtitles(
                subtitles, imdb_id, season, episode
            )

        return [sub["path"] for sub in subtitles]
