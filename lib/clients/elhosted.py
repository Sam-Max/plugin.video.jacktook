import json
import re
import requests
from lib.utils.kodi_utils import convert_size_to_bytes, translation


class Elfhosted:
    def __init__(self, host, notification) -> None:
        self.host = host.rstrip("/")
        self._notification = notification

    def search(self, imdb_id, mode, media_type, season, episode):
        try:
            if mode == "tv" or media_type == "tv":
                url = f"{self.host}/stream/series/{imdb_id}:{season}:{episode}.json"
            elif mode == "movie" or media_type == "movie" or mode == "multi":
                url = f"{self.host}/stream/{mode}/{imdb_id}.json"
            res = requests.get(url, timeout=10)
            if res.status_code != 200:
                return
            response = self.parse_response(res)
            return response
        except Exception as e:
            self._notification(f"{translation(30231)}: {str(e)}")

    def parse_response(self, res):
        res = json.loads(res.text)
        results = []
        for item in res["streams"]:
            parsed_item = self.parse_stream_title(item["title"])
            results.append(
                {
                    "title": parsed_item["title"],
                    "qualityTitle": "",
                    "indexer": "Elfhosted",
                    "guid": item["infoHash"],
                    "infoHash": item["infoHash"],
                    "size": parsed_item["size"],
                    "seeders": 0,
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

        return {
            "title": name,
            "size": size,
        }
