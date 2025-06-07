import json
import os

from lib.clients.aisubtrans.deepl import DeepLTranslator
from lib.clients.aisubtrans.opensubstremio import OpenSubtitleStremioClient
from lib.utils.kodi.utils import (
    ADDON_PROFILE_PATH,
    get_language_code,
    get_setting,
    kodilog,
)

import xbmc


class SubtitleManager:
    def __init__(self, kodi_player, notification):
        self.player = kodi_player
        self.notification = notification
        self.sub_client = OpenSubtitleStremioClient(notification)
        self.translator = DeepLTranslator(notification)

    def json_rpc(self, method, params=None):
        request_data = {
            "jsonrpc": "2.0",
            "method": method,
            "id": 1,
            "params": params or {},
        }
        response = json.loads(xbmc.executeJSONRPC(json.dumps(request_data)))
        if "error" in response:
            self.log(
                f"JsonRPC Error {response['error']['code']}: {response['error']['message']}",
                "debug",
            )
        return response.get("result", {})

    def convert_language_iso(self, from_value):
        return xbmc.convertLanguage(from_value, xbmc.ISO_639_1)

    def get_kodi_preferred_subtitle_language(self, iso_format=False):
        subtitle_language = self.json_rpc(
            "Settings.GetSettingValue", {"setting": "locale.subtitlelanguage"}
        )

        if subtitle_language["value"] in ["forced_only", "original", "default", "none"]:
            return subtitle_language["value"]
        if iso_format:
            return self.convert_language_iso(subtitle_language["value"])
        else:
            return subtitle_language["value"]

    def download_and_set_subtitles(self):
        if not get_setting("subtitle_enabled"):
            return

        subtitle_language = get_setting("subitle_language")
        if subtitle_language != "None":
            language_code = get_language_code(subtitle_language)

            kodilog(f"Language: {language_code}")

            subs_paths = self.download_subtitles(language_code)
            if subs_paths:
                self.player.list_item.setSubtitles(subs_paths)
                self.player.setSubtitleStream(1)
                self.player.showSubtitles(True)

                self.notification("Subtitles loaded...")

    def download_subtitles(self, lang):
        data = self.player.data
        mode = data.get("mode")
        imdb_id = data.get("imdb_id")
        episode = data.get("episode")
        season = data.get("season")

        if not imdb_id:
            kodilog("Not supported video item")
            return

        if mode == "tv":
            folder_path = f"{ADDON_PROFILE_PATH}/{imdb_id}/{season}"
        else:
            folder_path = f"{ADDON_PROFILE_PATH}/{imdb_id}"

        if os.path.exists(folder_path):
            kodilog("Loading subtitles from local folder...")
            return [
                os.path.join(folder_path, f)
                for f in os.listdir(folder_path)
                if f.endswith(".srt")
            ]
        else:
            subtitles = self.sub_client.get_subtitles(
                mode,
                imdb_id,
                season,
                episode,
                lang,
            )

            if subtitles:
                if not os.path.exists(folder_path):
                    os.makedirs(folder_path)

                    for count, sub in enumerate(subtitles):
                        self.sub_client.download_subtitle(
                            sub,
                            count,
                            imdb_id,
                            season=season,
                            episode=episode,
                        )

                if get_setting("deepl_enabled"):
                    return self.translator.process_subtitles(
                        subtitles, imdb_id, season, episode
                    )

                return [sub["path"] for sub in subtitles]
