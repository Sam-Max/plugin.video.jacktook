import json
import re
import requests
from lib.api.jacktook.kodi import kodilog
from lib.utils.kodi_utils import convert_size_to_bytes, translation
from lib.utils.utils import USER_AGENT_HEADER
from requests import Session


class MediaFusion:
    def __init__(self, host, manifest_url, notification) -> None:
        self.host = host.rstrip("/")
        self.api_key = self.extract_api_key(manifest_url)
        self._notification = notification
        self.session = Session()

    def extract_api_key(self, manifest_url):
        return (
            manifest_url.replace(self.host, "").replace("manifest.json", "").strip("/")
        )

    def search(self, imdb_id, mode, media_type, season, episode):
        try:
            if mode == "tv" or media_type == "tv":
                url = f"{self.host}/{self.api_key}/stream/series/{imdb_id}:{season}:{episode}.json"
            elif mode == "movies" or media_type == "movies":
                url = f"{self.host}/{self.api_key}/stream/movie/{imdb_id}.json"
            kodilog(url)
            res = self.session.get(url, headers=USER_AGENT_HEADER, timeout=10)
            if res.status_code != 200:
                return
            return self.parse_response(res)
        except Exception as e:
            self._notification(f"{translation(30228)}: {str(e)}")

    def parse_response(self, res):
        res = json.loads(res.text)
        kodilog(res)
        kodilog("mediafusion::parse_response")
        results = []
        for item in res["streams"]:
            info_hash = self.extract_info_hash(item)
            parsed_item = self.parse_stream_title(item)
            results.append(
                {
                    "title": parsed_item["title"],
                    "type": "Torrent",
                    "indexer": "MediaFusion",
                    "guid": info_hash,
                    "infoHash": info_hash,
                    "size": parsed_item["size"],
                    "seeders": parsed_item["seeders"],
                    "languages": parsed_item["languages"],
                    "fullLanguages": "",
                    "provider": parsed_item["provider"],
                    "publishDate": "",
                    "peers": 0,
                }
            )
        kodilog(results)
        return results

    def extract_info_hash(self, item):
        if "url" in item:
            query = requests.utils.urlparse(item["url"]).query
            params = dict(i.split("=") for i in query.split("&"))
            info_hash = params["info_hash"]
        else:
            info_hash = item["infoHash"]
        return info_hash

    def parse_stream_title(self, item):
        description = item["description"].splitlines()
        title = description[0]
        provider = item["name"].split()[0].title()
        size = convert_size_to_bytes(self.extract_size_string(item["description"]))
        seeders = self.extract_seeders(item["description"])

        return {
            "title": title,
            "size": size,
            "seeders": seeders,
            "languages": [],
            "provider": provider,
        }

    def extract_size_string(self, details: str):
        size_match = re.search(r"💾 (\d+(?:\.\d+)?\s*(GB|MB))", details, re.IGNORECASE)
        return size_match.group(1) if size_match else ""

    def extract_seeders(self, details: str) -> int:
        seeders_match = re.search(r"👤 (\d+)", details)
        return int(seeders_match.group(1)) if seeders_match else 0
