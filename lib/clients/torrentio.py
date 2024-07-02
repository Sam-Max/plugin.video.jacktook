import json
import re
from lib.utils.countries import find_language_by_unicode
from lib.utils.kodi_utils import convert_size_to_bytes, translation
from lib.utils.general_utils import unicode_flag_to_country_code
from requests import Session

class Torrentio:
    def __init__(self, host, notification) -> None:
        self.host = host.rstrip("/")
        self._notification = notification
        self.session = Session()

    def search(self, imdb_id, mode, media_type, season, episode):
        try:
            if mode == "tv" or media_type == "tv" or mode == "anime":
                url = f"{self.host}/stream/series/{imdb_id}:{season}:{episode}.json"
            elif mode == "movie" or media_type == "movie" or mode == "multi":
                url = f"{self.host}/stream/{mode}/{imdb_id}.json"
            res = self.session.get(url, timeout=10)
            if res.status_code != 200:
                return
            return self.parse_response(res)
        except Exception as e:
            self._notification(f"{translation(30228)}: {str(e)}")

    def parse_response(self, res):
        res = json.loads(res.text)
        results = []
        for item in res["streams"]:
            parsed_item = self.parse_stream_title(item["title"])
            results.append(
                {
                    "title": parsed_item["title"],
                    "qualityTitle": "",
                    "indexer": "Torrentio",
                    "guid": item["infoHash"],
                    "infoHash": item["infoHash"],
                    "size": parsed_item["size"],
                    "seeders": parsed_item["seeders"],
                    "languages": parsed_item["languages"],
                    "fullLanguages": parsed_item["full_languages"],
                    "publishDate": "",
                    "peers": 0,
                }
            )
        return results

    def parse_stream_title(self, title):
        name = title.splitlines()[0]

        size_match = re.search(r"💾 (\d+(?:\.\d+)?\s*(GB|MB))", title, re.IGNORECASE)
        size = size_match.group(1) if size_match else ""
        size = convert_size_to_bytes(size)

        seeders_match = re.search(r"👤 (\d+)", title)
        seeders = int(seeders_match.group(1)) if seeders_match else None

        languages, full_languages = self.extract_languages(title)

        return {
            "title": name,
            "size": size,
            "seeders": seeders,
            "languages": languages,
            "full_languages": full_languages,
        }

    def extract_languages(self, title):
        languages = []
        full_languages = []
        # Regex to match unicode country flag emojis
        flag_emojis = re.findall(r"[\U0001F1E6-\U0001F1FF]{2}", title)
        if flag_emojis:
            for flag in flag_emojis:
                languages.append(unicode_flag_to_country_code(flag).upper())
                full_lang = find_language_by_unicode(flag)
                if (full_lang != None) and (full_lang not in full_languages):
                    full_languages.append(full_lang)
        return languages, full_languages