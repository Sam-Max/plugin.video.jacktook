import traceback
import requests
from lib.clients.aisubtrans.utils import get_deepl_language_code, slugify
from lib.utils.kodi.utils import (
    ADDON_PROFILE_PATH,
    get_setting,
    kodilog,
)
from os import path as ospath, stat
from time import sleep

import xbmcgui


def show_dialog(title, message):
    # Kodi Yes/No dialog
    dialog = xbmcgui.Dialog()
    return dialog.yesno(title, message)


class DeepLTranslator:
    def __init__(self, notification):
        self.base_url = "https://api-free.deepl.com/v2"
        self.api_key = get_setting("deepl_api_key")
        self.target_lang = get_setting("deepl_target_language")
        self.notification = notification

    def _handle_deepl_response(self, response, context=""):
        """
        Handle DeepL API responses, showing a Kodi dialog and logging errors for non-200 codes.
        Returns True if response is OK, otherwise False.
        """
        if response.status_code == 200:
            return True

        status_messages = {
            400: "Bad request. The request was unacceptable, often due to missing a required parameter.",
            403: "Authorization failed. Check your DeepL API key.",
            404: "The requested resource could not be found.",
            413: "The uploaded file is too large.",
            429: "Too many requests. You have hit the rate limit.",
            456: "Quota exceeded. You have used up your translation quota.",
            503: "DeepL service is temporarily unavailable. Please try again later.",
        }
        user_message = status_messages.get(
            response.status_code,
            f"Unexpected error occurred (status code: {response.status_code}).",
        )

        msg = f"DeepL API error during {context}.\n" f"{user_message}\n\n"
        self.notification(heading="DeepL API Error", message=msg)
        return False

    def download_and_save_translation(
        self,
        idx,
        imdb_id,
        season,
        episode,
        lang_name="en",
        document_id=None,
        document_key=None,
    ):
        """
        Download the translated document from DeepL and save it as an .srt file.
        The file path is determined based on whether season/episode info is provided.
        """
        if season and episode:
            new_subtitle_file_path = (
                f"{ADDON_PROFILE_PATH}subtitles/{imdb_id}/{season}/"
                f"Translated_Subtitle No.{idx}.S{season}E{episode}.{lang_name}.srt"
            )
        elif season:
            new_subtitle_file_path = (
                f"{ADDON_PROFILE_PATH}subtitles/{imdb_id}/{season}/"
                f"Translated_Subtitle No.{idx}.S{season}.{lang_name}.srt"
            )
        else:
            new_subtitle_file_path = f"{ADDON_PROFILE_PATH}subtitles/{imdb_id}/Translated_Subtitle No.{idx}.{lang_name}.srt"

        # Ensure the file path is safe
        new_subtitle_file_path = slugify(new_subtitle_file_path)

        kodilog(f"Saving translated subtitle to: {new_subtitle_file_path}")

        url = f"{self.base_url}/document/{document_id}/result"
        headers = {
            "Authorization": f"DeepL-Auth-Key {self.api_key}",
            "Content-Type": "application/json",
        }

        response = requests.post(
            url, json={"document_key": document_key}, headers=headers
        )
        if not self._handle_deepl_response(response, "result download"):
            raise Exception("DeepL API error during result download")

        with open(new_subtitle_file_path, "wb") as f:
            f.write(response.content)

        kodilog(f"Translation saved to: {new_subtitle_file_path}")

        return new_subtitle_file_path

    def has_sufficient_api_characters(self, subtitle_paths, api_characters_remaining):
        """
        Check if the total character count across subtitle files is within API limits.
        """
        total_character_count = 0
        for file_path in subtitle_paths:
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

        if api_characters_remaining > total_character_count:
            kodilog("Sufficient API characters remaining. Proceeding with translation.")
            return True
        else:
            kodilog(
                f"Insufficient API characters remaining. Required: {total_character_count}, Available: {api_characters_remaining}"
            )
            return False

    def validate_file_limits(self, file_path):
        """
        Check if a file meets size and character count limits.
        Raises Exception and notifies the user if not.
        """
        MAX_FILE_SIZE_KB = 150
        MAX_CHARACTERS = 1000000

        stats = stat(file_path)
        file_size_kb = stats.st_size / 1024

        if file_size_kb > MAX_FILE_SIZE_KB:
            msg = f"File size ({file_size_kb:.2f} KB) exceeds the limit of {MAX_FILE_SIZE_KB} KB"
            self.notification(msg)
            raise Exception(msg)

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        character_count = len(content)

        if character_count > MAX_CHARACTERS:
            msg = f"Character count ({character_count}) exceeds the limit of {MAX_CHARACTERS}"
            self.notification(msg)
            raise Exception(msg)

        kodilog(
            f"File check passed: Size={file_size_kb:.2f}KB, Characters={character_count}"
        )

    def filter_files_within_limits(self, file_paths):
        """
        Returns a list of file paths that are within the allowed limits.
        Notifies the user for each file that is skipped.
        """
        valid_files = []
        for file_path in file_paths:
            try:
                self.validate_file_limits(file_path)
                valid_files.append(file_path)
            except Exception as e:
                # Notification already shown in validate_file_limits
                kodilog(f"File skipped due to limits: {file_path} ({e})")
        return valid_files

    def get_document_status(self, document_id, document_key):
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

        if not self._handle_deepl_response(response, "status check"):
            raise Exception("DeepL API error during status check")

        data = response.json()

        return data

    def wait_until_translation_complete(self, document_id, document_key):
        while True:
            status = self.get_document_status(document_id, document_key)
            if status.get("status") == "done":
                kodilog(f"Translation completed for document {document_id}")
                return status
            elif status.get("status") == "error":
                msg = f"Translation failed for document {document_id}: {status.get('message')}"
                kodilog(msg)
                raise Exception(f"Translation failed: {status.get('message')}")
            sleep(5)  # Corrected: sleep expects seconds, not ms

    def calculate_translation_cost(self, subtitle_paths):
        # DeepL API pricing (example, update with your actual pricing)
        # Free: 500,000 chars/month, paid: $20 per 1,000,000 chars (as of 2024)
        PRICE_PER_MILLION = 20.0  # USD per 1,000,000 chars

        total_characters = 0
        for file_path in subtitle_paths:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                total_characters += len(content)
            except Exception as error:
                kodilog(
                    f"Error reading file for cost calculation: {file_path}: {error}"
                )

        estimated_cost = (total_characters / 1_000_000) * PRICE_PER_MILLION
        return total_characters, estimated_cost

    def get_free_characters_left(self):
        """
        Query DeepL API for remaining free characters.
        Returns the number of free characters left, or 0 if unavailable.
        """
        url = f"{self.base_url}/usage"
        headers = {"Authorization": f"DeepL-Auth-Key {self.api_key}"}
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                # For free accounts, 'character_limit' and 'character_count' are present
                limit = data.get("character_limit", 0)
                used = data.get("character_count", 0)
                return max(0, limit - used)
        except Exception as e:
            kodilog(f"Error fetching DeepL usage: {e}")
        return 0

    def prompt_user_for_cost(self, subtitle_paths):
        """
        Show a dialog to the user with the estimated translation cost and ask for confirmation.
        Only show cost if free usage is exhausted.
        Returns True if user confirms, False otherwise.
        """
        free_chars_left = self.get_free_characters_left()
        total_characters, estimated_cost = self.calculate_translation_cost(
            subtitle_paths
        )

        if free_chars_left > total_characters:
            message = (
                f"Free DeepL usage available!\n"
                f"Characters left in free quota: {free_chars_left}\n"
                f"Characters to translate: {total_characters}\n\n"
                "Do you want to proceed with the translation?"
            )
            return show_dialog("Free DeepL Usage", message)

        message = (
            f"Total characters to translate: {total_characters}\n"
            f"Estimated cost: ${estimated_cost:.2f} USD\n\n"
            "Do you want to proceed with the translation?"
        )
        return show_dialog("Translation Cost", message)

    def translate_file(self, filepath, idx, imdbid, season, episode):
        """
        Upload a document for translation, wait for completion, then download and save the result.
        """
        try:
            self.notification("Translating subtitle...")
            url = f"{self.base_url}/document"
            with open(filepath, "rb") as file_handle:
                files = {
                    "file": (
                        ospath.basename(filepath),
                        file_handle,
                        "application/octet-stream",
                    )
                }

                kodilog(f"Target language: {get_deepl_language_code(self.target_lang)}")
                data = {"target_lang": get_deepl_language_code(self.target_lang)}

                headers = {"Authorization": f"DeepL-Auth-Key {self.api_key}"}

                response = requests.post(url, files=files, data=data, headers=headers)

            kodilog("Raw response content: " + response.text)

            if not self._handle_deepl_response(response, "document upload"):
                return None

            upload_data = response.json()

            if "document_id" not in upload_data or "document_key" not in upload_data:
                raise Exception(f"Invalid response from document upload: {upload_data}")

            document_id = upload_data["document_id"]
            document_key = upload_data["document_key"]

            self.wait_until_translation_complete(document_id, document_key)

            self.notification("Translation done.")

            return self.download_and_save_translation(
                idx,
                imdbid,
                season,
                episode,
                lang_name=self.target_lang,
                document_id=document_id,
                document_key=document_key,
            )
        except Exception as error:
            kodilog(f"Error in translate_file: {error}")
            raise

    def translate_multiple_subtitles(self, sub_paths, imdbid, season, episode):
        """
        Process multiple subtitle files by translating each one.
        Only files within limits are processed.
        """
        # Filter files within limits and notify user for skipped files
        valid_sub_paths = self.filter_files_within_limits(sub_paths)
        if not valid_sub_paths:
            self.notification("No subtitle files are within the allowed limits.")
            return []

        # Prompt user for cost before proceeding
        if not self.prompt_user_for_cost(valid_sub_paths):
            kodilog("User cancelled translation after cost prompt.")
            return []
        translated_subtitles = []

        for idx, path in enumerate(valid_sub_paths):
            try:
                translated_sub = self.translate_file(path, idx, imdbid, season, episode)
                if translated_sub:
                    translated_subtitles.append(translated_sub)
            except Exception as error:
                kodilog(traceback.format_exc())
                kodilog(f"Subtitle translate error: {error}")

        return translated_subtitles
