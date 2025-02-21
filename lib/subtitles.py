import json
import os
import traceback
import requests
from lib.api.jacktook.kodi import kodilog
from lib.utils.kodi_utils import (
    ADDON_PATH,
    ADDON_PROFILE_PATH,
    get_deepl_language_code,
    get_language_code,
    get_setting,
    set_setting,
    sleep,
)
from lib.utils.utils import USER_AGENT_STRING
import xbmc
import xbmcgui


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
            folder_path = f"{ADDON_PROFILE_PATH}/{imdb_id}/{episode}"
        else:
            folder_path = f"{ADDON_PROFILE_PATH}/{imdb_id}"

        if os.path.exists(folder_path):
            kodilog("Loading subtitles from local folder")
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

                download_subtitles = [
                    self.sub_client.download_subtitle(
                        sub["url"], count, imdb_id, lang=sub["lang"], episode=episode
                    )
                    for count, sub in enumerate(subtitles)
                ]
            
                if get_setting("deepl_enabled"):
                    return self.translator.process_subtitles(download_subtitles, imdb_id, season, episode)

                return download_subtitles

class DeepLTranslator:
    def __init__(self, notification):
        self.base_url = "https://api-free.deepl.com/v2"
        self.api_key = get_setting("deepl_api_key")
        self.target_lang = get_setting("deepl_target_language")
        self.notification = notification

    def save_translated_subs(
        self,
        count,
        imdbid,
        season,
        episode,
        document_id,
        document_key,
    ):
        """
        Download the translated document from DeepL and save it as an .srt file.
        The file path is determined based on whether season/episode info is provided.
        """
        if season and episode:
            new_subtitle_file_path = (
                f"{ADDON_PROFILE_PATH}/{imdbid}/{season}/subtitle.translated.{episode}.{count}.srt"
            )
        else:
            new_subtitle_file_path = (
                f"{ADDON_PROFILE_PATH}/{imdbid}/subtitle.translated.{count}.srt"
            )

        url = f"{self.base_url}/document/{document_id}/result"
        headers = {
            "Authorization": f"DeepL-Auth-Key {self.api_key}",
            "Content-Type": "application/json",
        }
        
        response = requests.post(url, json={"document_key": document_key}, headers=headers)
        if response.status_code != 200:
            error_text = response.text
            kodilog(f"DeepL API error response: {error_text}")
            raise Exception("DeepL API error during result download")
        
        os.makedirs(os.path.dirname(new_subtitle_file_path), exist_ok=True)
        
        with open(new_subtitle_file_path, "wb") as f:
            f.write(response.content)
        
        kodilog(f"Translation saved to: {new_subtitle_file_path}")

        return new_subtitle_file_path

    def check_remaining_api(self, subtitles, apikeyremaining):
        """
        Check the total character count across subtitle files to ensure it is within your API limits.
        """
        filepaths = subtitles 

        total_character_count = 0
        for file_path in filepaths:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                lines = content.split("\n")
                iscount = True
                istimecode = False
                istext = False
                characters = []
                textcount = 0

                for line in lines:
                    if line.strip() == "":
                        iscount = True
                        istimecode = False
                        istext = False
                        textcount = 0
                    elif iscount:
                        iscount = False
                        istimecode = True
                    elif istimecode:
                        istimecode = False
                        istext = True
                    elif istext:
                        if textcount == 0:
                            characters.append(line)
                        else:
                            characters[-1] += " \n" + line
                        textcount += 1

                for text in characters:
                    total_character_count += len(text)
            except Exception as error:
                kodilog(f"Error processing subtitle file {file_path}: {error}")

        kodilog(f"Total character count for translation: {total_character_count}")

        if apikeyremaining > total_character_count:
            kodilog("Sufficient API characters remaining. Proceeding with translation.")
            return True
        else:
            kodilog(
                    f"Insufficient API characters remaining. Required: {total_character_count}, Available: {apikeyremaining}"
                )
            return False

    def check_file_limits(self, file_path):
        """
        Check if a file meets size and character count limits.
        """
        MAX_FILE_SIZE_KB = 150
        MAX_CHARACTERS = 1000000

        stats = os.stat(file_path)
        file_size_kb = stats.st_size / 1024

        if file_size_kb > MAX_FILE_SIZE_KB:
            msg = f"File size ({file_size_kb:.2f} KB) exceeds the limit of {MAX_FILE_SIZE_KB} KB"
            raise Exception(msg)

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        character_count = len(content)

        if character_count > MAX_CHARACTERS:
            msg = f"Character count ({character_count}) exceeds the limit of {MAX_CHARACTERS}"
            raise Exception(msg)

        kodilog(f"File check passed: Size={file_size_kb:.2f}KB, Characters={character_count}")

    def check_status(self, document_id, document_key):
        """
        Check the status of a document translation.
        """
        url = f"{self.base_url}/document/{document_id}"
        headers = {
            "Authorization": f"DeepL-Auth-Key {self.api_key}",
            "Content-Type": "application/json",
        }
        response = requests.get(url, params={"document_key": document_key}, headers=headers)
        
        kodilog("Check status response text: " + response.text)

        if response.status_code != 200:
            text = response.text
            kodilog(f"DeepL API error response: {text}")
            raise Exception("DeepL API error during status check")
        
        data = response.json()
        
        return data

    def wait_for_translation(self, document_id, document_key):
        """
        Poll DeepL until the translation is complete.
        """
        while True:
            status = self.check_status(document_id, document_key)
            if status.get("status") == "done":
                kodilog(f"Translation completed for document {document_id}")
                return status
            elif status.get("status") == "error":
                msg = f"Translation failed for document {document_id}: {status.get('message')}"
                kodilog(msg)
                raise Exception(f"Translation failed: {status.get('message')}")
            sleep(5000) 

    def translate_document(self, filepath, imdbid, season, episode):
        """
        Upload a document for translation, wait for completion, then download and save the result.
        """
        try:
            self.notification("Translating subtitle...")
            self.check_file_limits(file_path=filepath)
            # Prepare multipart form data for document upload.
            url = f"{self.base_url}/document"
            files = {
                "file": (os.path.basename(filepath), open(filepath, "rb"), "application/octet-stream")
            }
            
            kodilog(f"Target language: {get_deepl_language_code(self.target_lang)}")
            data = {"target_lang": get_deepl_language_code(self.target_lang)}

            headers = {"Authorization": f"DeepL-Auth-Key {self.api_key}"}

            upload_response = requests.post(url, files=files, data=data, headers=headers)

            kodilog("Raw response content: " + upload_response.text)

            if upload_response.status_code != 200:
                kodilog(f"Error uploading document: {upload_response.text}")
                raise Exception("Error uploading document")
            
            upload_data = upload_response.json()

            if "document_id" not in upload_data or "document_key" not in upload_data:
                raise Exception(f"Invalid response from document upload: {upload_data}")

            document_id = upload_data["document_id"]
            document_key = upload_data["document_key"]

            self.wait_for_translation(document_id, document_key)

            self.notification("Translation done.")

            return self.save_translated_subs(1, imdbid, season, episode, document_id, document_key)
        except Exception as error:
            kodilog(f"Error in translate_document: {error}")
            raise

    def process_subtitles(self, filepaths, imdbid, season, episode):
        """
        Process multiple subtitle files by translating each one.
        """
        translated_subtitles = []
        for fp in filepaths:
            try:
                translated_sub = self.translate_document(fp, imdbid, season, episode)
                translated_subtitles.append(translated_sub)
            except Exception as error:
                traceback.print_exc()
                self.notification(f"Subtitle translate error: {error}")
        return translated_subtitles


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
                        fallback_language = get_setting("subitle_fallback_language")
                        if fallback_language != "None":
                            language_code = get_language_code(fallback_language)
                            subtitles = [
                                s for s in subtitles_list if s["lang"] == language_code
                            ]
                            
                            if not subtitles:
                                self.notification("No subtitles found for language")
                                return

                            if get_setting("deepl_enabled"):
                                subtitles_items = [xbmcgui.ListItem(label=f"Subtitle No. {e}", label2=f"{s["url"]}") for e, s in enumerate(subtitles_list)]
                                dialog = xbmcgui.Dialog()
                                selected_indexes = dialog.multiselect(
                                    "Subtitles Selection",
                                    subtitles_items,
                                    useDetails=True,
                                )

                                if selected_indexes is None:
                                    return []

                                subtitles = [
                                    subtitles[index] for index in selected_indexes
                                ]
                        else:
                            self.notification("No subtitles found for language")
                            return
                    return subtitles
                else:
                    self.notification(f"No subtitles found")
                    return
            else:
                self.notification(
                    f"Failed to fetch subtitles, status code {response.status_code}"
                )
                raise
        except Exception as e:
            self.notification(f"Failed to fetch subtitles: {e}")
            raise

    def download_subtitle(self, subtitle_url, index, imdb_id, lang, episode=None):
        try:
            response = requests.get(subtitle_url, stream=True)
            if response.status_code == 200:
                file_path = (
                    f"{ADDON_PROFILE_PATH}/{imdb_id}/{episode}/subtitle.E{episode}.{index}.{lang}.srt"
                    if episode
                    else f"{ADDON_PROFILE_PATH}/{imdb_id}/subtitle.{index}.{lang}.srt"
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
