import re
from typing import List, Dict, Tuple, Optional, Any, Callable

from lib.clients.base import BaseClient, TorrentStream
from lib.utils.localization.countries import find_language_by_unicode
from lib.utils.kodi.utils import convert_size_to_bytes, kodilog, translation
from lib.utils.general.utils import USER_AGENT_HEADER, unicode_flag_to_country_code


class Torrentio(BaseClient):
    def __init__(self, host: str, notification: Callable) -> None:
        super().__init__(host, notification)

    def search(
        self,
        imdb_id: str,
        mode: str,
        media_type: str,
        season: Optional[int],
        episode: Optional[int],
    ) -> Optional[List[TorrentStream]]:
        try:
            kodilog(f"Searching for {imdb_id} on Torrentio")
            if mode == "tv" or media_type == "tv":
                url = f"{self.host}/stream/series/{imdb_id}:{season}:{episode}.json"
            elif mode == "movies" or media_type == "movies":
                url = f"{self.host}/stream/{mode}/{imdb_id}.json"
            else:
                self.handle_exception(translation(30228))
                return None
            
            res = self.session.get(url, headers=USER_AGENT_HEADER, timeout=10)
            if res.status_code != 200:
                return
            return self.parse_response(res)
        except Exception as e:
            self.handle_exception(f"{translation(30228)}: {str(e)}")

    def parse_response(self, res: Any) -> List[TorrentStream]:
        res = res.json()
        results = []
        for item in res["streams"]:
            parsed_item = self.parse_stream_title(item["title"])
            results.append(
                TorrentStream(
                    title=parsed_item["title"],
                    type="Torrent",
                    indexer="Torrentio",
                    guid=item["infoHash"],
                    infoHash=item["infoHash"],
                    size=parsed_item["size"],
                    seeders=parsed_item["seeders"],
                    languages=parsed_item["languages"],
                    fullLanguages=parsed_item["full_languages"],
                    provider=parsed_item["provider"],
                    publishDate="",
                    peers=0,
                )
            )
        return results

    def parse_stream_title(self, title: str) -> Dict[str, Any]:
        name = title.splitlines()[0]

        size_match = re.search(r"💾 (\d+(?:\.\d+)?\s*(GB|MB))", title, re.IGNORECASE)
        size = size_match.group(1) if size_match else ""
        size = convert_size_to_bytes(size)

        seeders_match = re.search(r"👤 (\d+)", title)
        seeders = int(seeders_match.group(1)) if seeders_match else None

        languages, full_languages = self.extract_languages(title)

        provider = self.extract_provider(title)

        return {
            "title": name,
            "size": size,
            "seeders": seeders,
            "languages": languages,
            "full_languages": full_languages,
            "provider": provider,
        }

    def extract_languages(self, title: str) -> Tuple[List[str], List[str]]:
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

    def extract_provider(self, title: str) -> str:
        match = re.search(r"⚙.* ([^ \n]+)", title)
        return match.group(1) if match else ""
