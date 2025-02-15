import json
import os
import requests
from lib.api.jacktook.kodi import kodilog
from lib.utils.kodi_utils import (
    ADDON_PATH,
    ADDON_PROFILE_PATH,
    get_language_code,
    get_setting,
    notification,
    set_setting,
)
import xbmc


class SubtitleManager:
    def __init__(self, kodi_player):
        self.player = kodi_player
        self.sub_client = OpenSubtitleStremioClient(notification)

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
            language = get_language_code(subtitle_language)
        else:
            preferred_language = self.get_kodi_preferred_subtitle_language(
                iso_format=True
            )
            if preferred_language == "original":
                audio_streams = self.player.getAvailableAudioStreams()
                if not audio_streams or len(audio_streams) == 0:
                    return
                language = audio_streams[0]
            elif preferred_language == "default":
                language = xbmc.getLanguage(xbmc.ISO_639_2)
            elif preferred_language in ["none", "forced_only"]:
                return

        kodilog(f"Language: {language}")
        subtitle_streams = self.player.getAvailableSubtitleStreams()
        kodilog(f"SubtitleStreams: {subtitle_streams}")

        for index, stream in enumerate(subtitle_streams):
            if language in stream.lower():
                self.player.setSubtitleStream(index)
                self.player.showSubtitles(True)
                return

        subs_paths = self.download_subtitles(subtitle_language)
        self.player.list_item.setSubtitles(subs_paths)
        notification("Subtitles loaded...")

    def download_subtitles(self, lang):
        data = self.player.data
        mode = data.get("mode")
        imdb_id = data.get("imdb_id")
        title = data.get("title")
        episode = data.get("episode")
        season = data.get("season")

        if not imdb_id:
            kodilog("Not supported video item")
            return

        folder_path = f"{ADDON_PROFILE_PATH}/{imdb_id}"

        if os.path.exists(folder_path):
            return [f for f in os.listdir(folder_path) if f.endswith(".srt")]
        else:
            subtitles = self.sub_client.get_subtitles(
                mode,
                imdb_id,
                season,
                episode,
                lang,
            )

            if not os.path.exists(folder_path):
                os.makedirs(folder_path)

            return [
                self.sub_client.download_subtitle(
                    sub["url"], count, imdb_id, title, lang=sub["lang"], episode=episode
                )
                for count, sub in enumerate(subtitles)
            ]


class OpenSubtitleStremioClient:
    ADDON_BASE_URL = get_setting("subtitle_addon_host")

    def __init__(self, notification):
        self.notification = notification

    def get_subtitles(self, mode, imdb_id, season=None, episode=None, lang="eng"):
        if mode == "tv":
            url = f"{self.ADDON_BASE_URL}subtitles/series/{imdb_id}:{season}:{episode}.json"
        else:
            url = f"{self.ADDON_BASE_URL}subtitles/movie/{imdb_id}.json"

        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()

                kodilog(f"OpenSubtitles Subtitles Response: {data}")

                subtitles_list = data.get("subtitles", [])

                if subtitles_list:
                    subtitles = [s for s in subtitles_list if s["lang"] == lang]
                    if not subtitles:
                        kodilog(
                            "No subtitles found the selected language, using first available subtitle"
                        )
                        subtitles = [subtitles_list[0]]
                    return subtitles
                else:
                    self.notification(f"No subtitles found")
                    raise
            else:
                self.notification(
                    f"Failed to fetch subtitles, status code {response.status_code}"
                )
                raise
        except Exception as e:
            self.notification(f"Failed to fetch subtitles: {e}")
            raise

    def download_subtitle(
        self, subtitle_url, index, imdb_id, title, lang, episode=None
    ):
        try:
            response = requests.get(subtitle_url, stream=True)
            if response.status_code == 200:
                file_path = (
                    f"{ADDON_PROFILE_PATH}/{imdb_id}/{title}_{episode}_{index}_{lang}.srt"
                    if episode
                    else f"{ADDON_PROFILE_PATH}/{imdb_id}/{title}_{index}_{lang}.srt"
                )

                with open(file_path, "wb") as file:
                    file.write(response.content)
                return file_path
            else:
                self.notification(
                    f"Failed to download {subtitle_url}, status code {response.status_code}"
                )
                raise
        except Exception as e:
            self.notification(f"Subtitle download error for {subtitle_url}: {e}")
            raise


class OpenSubtitleOfficialClient:
    OPEN_SUBTITLES_BASE_URL = "https://api.opensubtitles.com/api/v1//subtitles/"
    OPEN_SUBTITLES_LOGIN_URL = "https://api.opensubtitles.com/api/v1/login"

    def __init__(self, notification):
        self.notification = notification
        self.username = get_setting("opensub_username")
        self.password = get_setting("opensub_password")
        self.token = get_setting("opensub_token")
        self.session_token = self.login()

    def login(self):
        if not self.token:
            data = {"username": self.username, "password": self.password}
            headers = {
                "Accept": "application/json",
                "Api-Key": "",
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT_STRING,
            }
            try:
                response = requests.post(
                    self.OPEN_SUBTITLES_BASE_URL, data=data, headers=headers
                )
                if response.status_code == 200:
                    response_data = response.json()
                    kodilog(f"OpenSubtitles Logging Response: {response_data}")
                    session_token = response_data.get("data", {}).get("token")
                    if session_token:
                        set_setting("opensub_token", session_token)
                        return session_token
                    else:
                        self.notification("Login failed, no token received.")
                        return
                else:
                    self.notification(
                        f"Login failed, status code {response.status_code}"
                    )
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
