from lib.utils.utils import USER_AGENT_HEADER
from lib.stremio.addons_manager import Addon
from lib.stremio.stream import Stream

from lib.api.jacktook.kodi import kodilog
from lib.utils.kodi_utils import convert_size_to_bytes
from lib.utils.language_detection import find_languages_in_string
import requests
import re


class StremioAddonClient:
    def __init__(self, addon: Addon):
        self.addon = addon

    def search(self, imdb_id, mode, media_type, season, episode):
        try:
            if mode == "tv" or media_type == "tv":
                if not self.addon.isSupported("stream", "series", "tt"):
                    return []
                url = f"{self.addon.url()}/stream/series/{imdb_id}:{season}:{episode}.json"
            elif mode == "movies" or media_type == "movies":
                if not self.addon.isSupported("stream", "movie", "tt"):
                    return []
                url = f"{self.addon.url()}/stream/movie/{imdb_id}.json"
            res = requests.get(url, headers=USER_AGENT_HEADER, timeout=10)
            if res.status_code != 200:
                return
            return self.parse_response(res)
        except Exception as e:
            kodilog(f"Error in {self.addon.manifest.name}: {str(e)}")

    def parse_response(self, res):
        res = res.json()
        kodilog(res)
        results = []
        for item in res["streams"]:
            stream = Stream(item)
            parsed = self.parse_torrent_description(stream.description)

            results.append(
                {
                    "title": stream.get_parsed_title(),
                    "type": "Torrent",
                    "indexer": self.addon.manifest.name.split(" ")[0],
                    "guid": stream.infoHash,
                    "infoHash": stream.infoHash,
                    "size": stream.get_parsed_size()
                    or item.get("sizebytes")
                    or parsed["size"],
                    "seeders": item.get("seed", 0) or parsed["seeders"],
                    "languages": parsed["languages"],  # [item.get("language", "")],
                    "fullLanguages": parsed["languages"],  # [item.get("language", "")],
                    "provider": parsed["provider"],
                    "publishDate": "",
                    "peers": 0,
                }
            )
        return results

    def parse_torrent_description(self, desc: str) -> dict:
        # Extract size
        size_pattern = r"💾 ([\d.]+ (?:GB|MB))"
        size_match = re.search(size_pattern, desc)
        size = size_match.group(1) if size_match else None
        if size:
            size = convert_size_to_bytes(size)

        # Extract seeders
        seeders_pattern = r"👤 (\d+)"
        seeders_match = re.search(seeders_pattern, desc)
        seeders = int(seeders_match.group(1)) if seeders_match else None

        # Extract provider
        provider_pattern = r"([🌐🔗⚙️])\s*([^🌐🔗⚙️]+)"
        provider_match = re.findall(provider_pattern, desc)

        words = [match[1].strip() for match in provider_match]
        if words:
            words = words[-1].splitlines()[0]

        provider = words

        return {
            "size": size or 0,
            "seeders": seeders or 0,
            "provider": provider or "",
            "languages": find_languages_in_string(desc),
        }
