import json
import re
from lib.api.jacktook.kodi import kodilog
from lib.clients.base import BaseClient
from lib.utils.countries import find_language_by_unicode
from lib.utils.kodi_utils import convert_size_to_bytes, translation
from lib.utils.utils import USER_AGENT_HEADER, unicode_flag_to_country_code


class Peerflix(BaseClient):
    def __init__(self, host, notification):
        super().__init__(host, notification)

    def search(self, imdb_id, mode, media_type, season, episode):
        try:
            if mode == "tv" or media_type == "tv":
                url = f"{self.host}/stream/series/{imdb_id}:{season}:{episode}.json"
            elif mode == "movies" or media_type == "movies":
                url = f"{self.host}/stream/movie/{imdb_id}.json"
            res = self.session.get(url, headers=USER_AGENT_HEADER, timeout=10)
            if res.status_code != 200:
                return
            return self.parse_response(res)
        except Exception as e:
            self.handle_exception(f"{translation(30228)}: {str(e)}")

    def parse_response(self, res):
        res = res.json()
        results = []
        for item in res["streams"]:
            results.append(
                {
                    "title": item["description"],
                    "type": "Torrent",
                    "indexer": "Peerflix",
                    "guid": item["infoHash"],
                    "infoHash": item["infoHash"],
                    "size":item["sizebytes"] or 0,
                    "seeders": item.get("seed", 0) or 0,
                    "languages": [item["language"]],
                    "fullLanguages": [item["language"]],
                    "provider": self.extract_provider(item["description"]),
                    "publishDate": "",
                    "peers": 0,
                }
            )
        return results

    def extract_provider(self, title):
        match = re.search(r"🌐.* ([^ \n]+)", title)
        return match.group(1) if match else ""
