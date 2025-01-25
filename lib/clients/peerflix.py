import re
from lib.clients.base import BaseClient
from lib.utils.kodi_utils import translation
from lib.utils.utils import USER_AGENT_HEADER


class Peerflix(BaseClient):
    def __init__(self, host, notification, language):
        super().__init__(host, notification)
        self.language = language.lower()

    def search(self, imdb_id, mode, media_type, season, episode):
        try:
            if mode == "tv" or media_type == "tv":
                url = f"{self.host}/language={self.language}/stream/series/{imdb_id}:{season}:{episode}.json"
            elif mode == "movies" or media_type == "movies":
                url = f"{self.host}/language={self.language}/stream/movie/{imdb_id}.json"
            res = self.session.get(url, headers=USER_AGENT_HEADER, timeout=10)
            if res.status_code != 200:
                return
            return self.parse_response(res)
        except Exception as e:
            self.handle_exception(f"{translation(30234)}: {str(e)}")

    def parse_response(self, res):
        res = res.json()
        results = []
        for item in res["streams"]:
            results.append(
                {
                    "title": item["title"].splitlines()[0],
                    "type": "Torrent",
                    "indexer": "Peerflix",
                    "guid": item["infoHash"],
                    "infoHash": item["infoHash"],
                    "size":item["sizebytes"] or 0,
                    "seeders": item.get("seed", 0) or 0,
                    "languages": [item["language"]],
                    "fullLanguages": [item["language"]],
                    "provider": self.extract_provider(item["title"]),
                    "publishDate": "",
                    "peers": 0,
                }
            )
        return results

    def extract_provider(self, title):
        match = re.search(r"🌐.* ([^ \n]+)", title)
        return match.group(1) if match else ""
