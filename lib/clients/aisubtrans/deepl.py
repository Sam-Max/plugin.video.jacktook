import traceback
import requests
from lib.clients.aisubtrans.utils import get_deepl_language_code
from lib.utils.kodi.utils import (
    ADDON_PROFILE_PATH,
    get_setting,
    kodilog,
)
from os import path as ospath, makedirs, stat
from time import sleep


class DeepLTranslator:
    def __init__(self, notification):
        self.base_url = "https://api-free.deepl.com/v2"
        self.api_key = get_setting("deepl_api_key")
        self.target_lang = get_setting("deepl_target_language")
        self.notification = notification

    def save_translated_subs(
        self,
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
            new_subtitle_file_path = f"{ADDON_PROFILE_PATH}/{imdbid}/{season}/subtitle.translated.{episode}.srt"
        else:
            new_subtitle_file_path = (
                f"{ADDON_PROFILE_PATH}/{imdbid}/subtitle.translated.srt"
            )

        url = f"{self.base_url}/document/{document_id}/result"
        headers = {
            "Authorization": f"DeepL-Auth-Key {self.api_key}",
            "Content-Type": "application/json",
        }

        response = requests.post(
            url, json={"document_key": document_key}, headers=headers
        )
        if response.status_code != 200:
            error_text = response.text
            kodilog(f"DeepL API error response: {error_text}")
            raise Exception("DeepL API error during result download")

        makedirs(ospath.dirname(new_subtitle_file_path), exist_ok=True)

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

        stats = stat(file_path)
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

        kodilog(
            f"File check passed: Size={file_size_kb:.2f}KB, Characters={character_count}"
        )

    def check_status(self, document_id, document_key):
        """
        Check the status of a document translation.
        """
        url = f"{self.base_url}/document/{document_id}"
        headers = {
            "Authorization": f"DeepL-Auth-Key {self.api_key}",
            "Content-Type": "application/json",
        }
        response = requests.get(
            url, params={"document_key": document_key}, headers=headers
        )

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
                "file": (
                    ospath.basename(filepath),
                    open(filepath, "rb"),
                    "application/octet-stream",
                )
            }

            kodilog(f"Target language: {get_deepl_language_code(self.target_lang)}")
            data = {"target_lang": get_deepl_language_code(self.target_lang)}

            headers = {"Authorization": f"DeepL-Auth-Key {self.api_key}"}

            response = requests.post(url, files=files, data=data, headers=headers)

            kodilog("Raw response content: " + response.text)

            if response.status_code != 200:
                kodilog(f"Error uploading document: {response.text}")
                raise Exception("Error uploading document")

            upload_data = response.json()

            if "document_id" not in upload_data or "document_key" not in upload_data:
                raise Exception(f"Invalid response from document upload: {upload_data}")

            document_id = upload_data["document_id"]
            document_key = upload_data["document_key"]

            self.wait_for_translation(document_id, document_key)

            self.notification("Translation done.")

            return self.save_translated_subs(
                imdbid, season, episode, document_id, document_key
            )
        except Exception as error:
            kodilog(f"Error in translate_document: {error}")
            raise

    def process_subtitles(self, subtitles, imdbid, season, episode):
        """
        Process multiple subtitle files by translating each one.
        """
        translated_subtitles = []

        for sub in subtitles:
            try:
                translated_sub = self.translate_document(
                    sub["url"], imdbid, season, episode
                )
                translated_subtitles.append(translated_sub)
            except Exception as error:
                kodilog(traceback.print_exc())
                kodilog(f"Subtitle translate error: {error}")

        return translated_subtitles
