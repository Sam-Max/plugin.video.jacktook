import requests
from lib.utils.kodi.utils import (
    ADDON_PROFILE_PATH,
    get_language_code,
    get_setting,
    kodilog,
)

import xbmcgui


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
                    filtered_subtitles = [
                        s for s in subtitles_list if s["lang"] == lang
                    ]
                    if not filtered_subtitles:
                        fallback_language = get_setting("subitle_fallback_language")
                        if fallback_language != "None":
                            language_code = get_language_code(fallback_language)
                            filtered_subtitles = [
                                s for s in subtitles_list if s["lang"] == language_code
                            ]

                            if not filtered_subtitles:
                                self.notification("No subtitles found for language")
                                return

                            if get_setting("deepl_enabled"):
                                subtitles_items = [
                                    xbmcgui.ListItem(
                                        label=f"Subtitle No. {e}", label2=f"{s['url']}"
                                    )
                                    for e, s in enumerate(filtered_subtitles)
                                ]
                                dialog = xbmcgui.Dialog()
                                selected_indexes = dialog.multiselect(
                                    "Subtitles Selection",
                                    subtitles_items,
                                    useDetails=True,
                                )

                                if selected_indexes is None:
                                    return []

                                return [
                                    filtered_subtitles[index]
                                    for index in selected_indexes
                                ]
                        else:
                            self.notification("No subtitles found for language")
                            return
                    return filtered_subtitles
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

    def download_subtitle(self, sub, index, imdb_id, season=None, episode=None):
        try:
            response = requests.get(sub["url"], stream=True)
            if response.status_code == 200:
                file_path = (
                    f"{ADDON_PROFILE_PATH}/{imdb_id}/{season}/subtitle.E{episode}.{index}.{sub['lang']}.srt"
                    if episode
                    else f"{ADDON_PROFILE_PATH}/{imdb_id}/subtitle.{index}.{sub['lang']}.srt"
                )

                with open(file_path, "wb") as file:
                    file.write(response.content)

                sub["url"] = file_path
            else:
                self.notification(
                    f"Failed to download {sub['url']}, status code {response.status_code}"
                )
                raise
        except Exception as e:
            self.notification(f"Subtitle download error for {sub['url']}: {e}")
            raise
