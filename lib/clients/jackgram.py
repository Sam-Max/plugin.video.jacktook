import json
from lib.api.jacktook.kodi import kodilog
from lib.clients.base import BaseClient
from lib.utils.kodi_utils import translation


class Jackgram(BaseClient):
    def __init__(self, host, notification):
        super().__init__(host, notification)

    def search(self, tmdb_id, query, mode, media_type, season, episode):
        try:
            kodilog(f"Searching {query} on Jackgram")

            if mode == "tv" or media_type == "tv":
                url = f"{self.host}/stream/series/{tmdb_id}:{season}:{episode}.json"
            elif mode == "movies" or media_type == "movies":
                url = f"{self.host}/stream/movie/{tmdb_id}.json"
            else:
                url = f"{self.host}/search?query={query}"

            kodilog(f"Jackgram URL: {url}")
            kodilog(f"Jackgram mode: {mode}")

            res = self.session.get(url, timeout=10)
            if res.status_code != 200:
                return
            
            if mode in ["tv", "movies"]:
                return self.parse_response(res)
            else:
                response = self.parse_response_search(res)
                kodilog(f"Jackgram search response: {response}")
                return response
        except Exception as e:
            self.handle_exception(f"{translation(30232)}: {e}")

    def get_latest(self, page):
        url = f"{self.host}/stream/latest?page={page}"
        res = self.session.get(url, timeout=10)
        if res.status_code != 200:
            return
        return res.json()

    def get_files(self, page):
        url = f"{self.host}/stream/files?page={page}"
        res = self.session.get(url, timeout=10)
        if res.status_code != 200:
            return
        return res.json()

    def parse_response(self, res):
        res = res.json()
        results = []
        for item in res["streams"]:
            results.append(
                {
                    "title": item["title"],
                    "type": "Direct",
                    "indexer": item["name"],
                    "size": item["size"],
                    "publishDate": item["date"],
                    "duration": item["duration"],
                    "downloadUrl": item["url"],
                }
            )
        return results

    def parse_response_search(self, res):
        res = res.json()
        results = []
        for item in res["results"]:
            if item.get("type") == "file":
                results.append(self._extract_file_info(item))
            else:
                for file in item.get("files", []):
                    results.append(self._extract_file_info(file))
        return results

    def _extract_file_info(self, file):
        return {
            "title": file.get("title", ""),
            "type": "Direct",
            "indexer": file.get("name", ""),
            "size": file.get("size", ""),
            "publishDate": file.get("date", ""),
            "duration": file.get("duration", ""),
            "downloadUrl": file.get("url", ""),
        }
