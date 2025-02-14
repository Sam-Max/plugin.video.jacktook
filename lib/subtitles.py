import json
import os

import requests
from lib.api.jacktook.kodi import kodilog
from lib.utils.kodi_utils import ADDON_PATH, get_setting, notification
import xbmc

from lib.utils.utils import USER_AGENT_STRING


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


class DeepLTranslator:
    API_ENDPOINT = "https://api-free.deepl.com/v2/translate"

    def __init__(self):
        self.DEEPL_API_KEY = get_setting("deepl_api_key")

    def translate_subtitle_file(self, subtitle_path, target_lang="EN"):
        if not os.path.exists(subtitle_path):
            notification(f"Subtitle file not found: {subtitle_path}")
            return

        try:
            with open(subtitle_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            notification(f"Error reading subtitle file: {e}")
            return

        # SRT files are split into blocks separated by blank lines.
        blocks = content.strip().split("\n\n")
        translated_blocks = []

        for block in blocks:
            lines = block.splitlines()
            # Expecting at least three lines: index, timestamp, and text.
            if len(lines) < 3:
                translated_blocks.append(block)
                continue

            index_line = lines[0]
            timestamp_line = lines[1]
            text_lines = lines[2:]

            # Combine text lines into a single block (preserving newline breaks).
            text_to_translate = "\n".join(text_lines)
            translated_text = self.translate_text(text_to_translate, target_lang)

            # Reconstruct the block.
            new_block = "\n".join([index_line, timestamp_line, translated_text])
            translated_blocks.append(new_block)

        translated_file_path = subtitle_path.replace(".srt", f"_{target_lang}.srt")

        try:
            with open(translated_file_path, "w", encoding="utf-8") as f:
                f.write("\n\n".join(translated_blocks))
            return translated_file_path
        except Exception as e:
            notification(f"Error writing translated subtitle file: {e}")
            return

    def translate_text(self, text, target_lang="EN"):
        data = {
            "auth_key": self.DEEPL_API_KEY,
            "text": text,
            "target_lang": target_lang,
            "preserve_formatting": 1,
        }
        try:
            response = requests.post(self.API_ENDPOINT, data=data)
            if response.status_code == 200:
                result = response.json()
                translations = result.get("translations")
                if translations:
                    return translations[0]["text"]
                else:
                    raise Exception("No translation returned by DeepL.")
            else:
                raise Exception(f"HTTP {response.status_code}: {response.text}")
        except Exception as e:
            notification(f"DeepL translation error: {e}")
            # Fallback: return the original text if an error occurs.
            return text


class OpenSubtitleClient:
    OPEN_SUBTITLES_BASE_URL = "https://opensubtitles-v3.strem.io/subtitles/"
    OPEN_SUBTITLES_LOGIN_URL = "https://api.opensubtitles.com/api/v1/login"

    def __init__(self, notification):
        self.notification = notification
        self.username = get_setting("opensub_username")
        self.password = get_setting("opensub_password")
        self.session_token = self.login()

    def login(self):
        data = {"username": self.username, "password": self.password}
        headers = {
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT_STRING,
        }
        try:
            response = requests.post(
                self.OPEN_SUBTITLES_BASE_URL, json=data, headers=headers
            )
            if response.status_code == 200:
                response_data = response.json()
                kodilog(f"OpenSubtitles Logging Response: {response_data}")
                session_token = response_data.get("data", {}).get("token")
                if session_token:
                    return session_token
                else:
                    self.notification("Login failed, no token received.")
                    return
            else:
                self.notification(f"Login failed, status code {response.status_code}")
                return
        except Exception as e:
            self.notification(f"Login error: {e}")
            return

    def get_subtitles(self, imdb_id, tmdb_id, season=None, episode=None):
        if not self.session_token:
            self.notification("You must log in first to fetch subtitles.")
            return

        params = {}

        if imdb_id:
            params["imdb_id"] = imdb_id
        elif tmdb_id:
            params["tmdb_id"] = tmdb_id

        if season:
            params["season_number"] = season
        if episode:
            params["episode_number"] = episode

        headers = {
            "Api-Key": self.session_token,
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT_STRING,
        }

        try:
            response = requests.get(
                self.OPEN_SUBTITLES_BASE_URL, params=params, headers=headers
            )
            if response.status_code == 200:
                data = response.json()
                kodilog(f"OpenSubtitles Subtitles Response: {data}")
                subtitles_list = data.get("subtitles", [])

                if subtitles_list:
                    subtitles = [s["url"] for s in subtitles_list if s["lang"] == "eng"]
                    if not subtitles:
                        kodilog(
                            "No English subtitles found, using first available subtitle"
                        )
                        subtitles = [subtitles_list[0]["url"]]

                    return subtitles[:1]
                else:
                    self.notification(f"No subtitles found")
                    return
            else:
                self.notification(
                    f"Failed to fetch subtitles, status code {response.status_code}"
                )
                return
        except Exception as e:
            self.notification(f"Failed to fetch subtitles: {e}")
            return

    def download_subtitle(self, subtitle_url, imdbid, episode=None):
        try:
            response = requests.get(subtitle_url, stream=True)
            if response.status_code == 200:
                file_path = (
                    f"{ADDON_PATH}/{imdbid}-subtitle_{episode}.srt"
                    if episode
                    else f"{ADDON_PATH}/{imdbid}-subtitle.srt"
                )

                with open(file_path, "wb") as file:
                    file.write(response.content)
                return file_path
            else:
                self.notification(
                    f"Failed to download {subtitle_url}, status code {response.status_code}"
                )
        except Exception as e:
            self.notification(f"Subtitle download error for {subtitle_url}: {e}")
