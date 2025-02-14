import json
import os
from lib.api.jacktook.kodi import kodilog
from lib.utils.kodi_utils import ADDON_PATH, get_setting, notification
import xbmc

class SubtitleManager:
    def __init__(self, kodi_player, sub_client, translator):
        self.player = kodi_player
        self.sub_client = sub_client
        self.translator = translator
        self.translate_subtitle = get_setting("translate_subtitle")

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

    def check_and_set_subtitles(self):
        preferred_language = self.get_kodi_preferred_subtitle_language(iso_format=True)

        if preferred_language == "original":
            audio_streams = self.player.getAvailableAudioStreams()
            if not audio_streams or len(audio_streams) == 0:
                return
            preferred_language = audio_streams[0]
        elif preferred_language == "default":
            preferred_language = xbmc.getLanguage(xbmc.ISO_639_2)
        elif preferred_language in ["none", "forced_only"]:
            return

        kodilog(f"preferred_language:  {preferred_language}")

        subtitle_streams = self.player.getAvailableSubtitleStreams()

        kodilog(f"subtitle_streams:  {subtitle_streams}")

        for index, stream in enumerate(subtitle_streams):
            if preferred_language in stream.lower():
                self.player.setSubtitleStream(index)
                self.player.showSubtitles(True)
                return

        # self.download_and_set_subtitles()

    def download_and_set_subtitles(self):
        data = self.player.data

        mode = data.get("mode", "")
        episode = data.get("episode", "")
        season = data.get("season", "")
        name = data.get("name", "")
        tmdb_id = data.get("tmdb_id")
        imdb_id = data.get("imdb_id")

        srt_path = (
            f"{ADDON_PATH}/{imdb_id}-subtitle_{episode}.srt"
            if episode
            else f"{ADDON_PATH}/{imdb_id}-subtitle.srt"
        )

        if os.path.exists(srt_path):
            self.player.setSubtitles(srt_path)
            self.player.showSubtitles(True)
            return

        subtitle_url = self.sub_client.get_subtitles(
            mode, imdb_id, season, episode, iso639_2="eng"
        )
        subtitle_path = self.sub_client.download_subtitle(
            subtitle_url, imdb_id, episode
        )

        if self.translate_subtitle:
            if not self.translator.DEEPL_API_KEY:
                notification("No API key set for DEEPL")
                raise ValueError("DeepL API key missing.")

            subtitle_path = self.translator.translate_subtitle_file(
                subtitle_path, target_lang="EN"
            )

        self.player.setSubtitles(subtitle_path)
        self.player.showSubtitles(True)