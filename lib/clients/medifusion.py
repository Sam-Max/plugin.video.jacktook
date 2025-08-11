import re
from typing import List, Dict, Any, Optional, Callable

from lib.clients.base import BaseClient, TorrentStream
from lib.utils.kodi.utils import convert_size_to_bytes, get_setting, translation
from lib.utils.general.utils import (
    MEDIA_FUSION_DEFAULT_KEY,
    USER_AGENT_HEADER,
    get_cached,
    set_cached,
)
from requests.utils import urlparse


class MediaFusion(BaseClient):
    def __init__(self, host: str, notification: Callable) -> None:
        super().__init__(host, notification)
        self.encryption_url = "https://mediafusion.elfhosted.com/encrypt-user-data"
        self.api_key = self.extract_api_key()

    def extract_api_key(self) -> str:
        if get_setting("real_debrid_enabled"):
            api_key = get_cached(path="md.rd.key")
            if api_key:
                return api_key
            config_json = self.get_config_json()
            config_json["streaming_provider"] = {
                "token": get_setting("real_debrid_token"),
                "service": "realdebrid",
                "only_show_cached_streams": True,
            }
            path = self.session.post(self.encryption_url, json=config_json, timeout=4.0)
            path = path.json()["encrypted_str"]
            api_key = (
                path.replace(self.host, "").replace("manifest.json", "").strip("/")
            )
            set_cached(data=api_key, path="md.rd.key")
            return api_key
        else:
            return MEDIA_FUSION_DEFAULT_KEY

    def get_config_json(self) -> Dict[str, Any]:
        return {
            "streaming_provider": {
                "token": "",
                "service": "",
                "only_show_cached_streams": False,
            },
            "enable_catalogs": False,
            "max_streams_per_resolution": 99,
            "torrent_sorting_priority": [],
            "certification_filter": ["Disable"],
            "nudity_filter": ["Disable"],
        }

    def search(
        self,
        imdb_id: str,
        mode: str,
        media_type: str,
        season: Optional[int],
        episode: Optional[int],
    ) -> Optional[List[TorrentStream]]:
        try:
            if mode == "tv" or media_type == "tv":
                url = f"{self.host}/{self.api_key}/stream/series/{imdb_id}:{season}:{episode}.json"
            elif mode == "movies" or media_type == "movies":
                url = f"{self.host}/{self.api_key}/stream/movie/{imdb_id}.json"
            else:
                self.handle_exception(translation(30233))
                return None
            
            res = self.session.get(url, headers=USER_AGENT_HEADER, timeout=10)
            if res.status_code != 200:
                return
            return self.parse_response(res.json())
        except Exception as e:
            self.handle_exception(f"{translation(30233)}: {str(e)}")

    def parse_response(self, res: Dict[str, Any]) -> List[TorrentStream]:
        results = []
        for item in res["streams"]:
            info_hash = self.extract_info_hash(item)
            parsed_item = self.parse_stream_title(item)
            results.append(
                TorrentStream(
                    title=parsed_item["title"],
                    type="Torrent",
                    indexer="MediaFusion",
                    guid=info_hash,
                    infoHash=info_hash,
                    size=parsed_item["size"],
                    seeders=parsed_item["seeders"],
                    languages=parsed_item["languages"],
                    provider=parsed_item["provider"],
                    publishDate="",
                    peers=0,
                    fullLanguages="",
                )
            )
        return results

    def extract_info_hash(self, item: Dict[str, Any]) -> str:
        if "url" in item:
            path = urlparse(item["url"]).path.split("/")
            info_hash = path[path.index("stream") + 1]
        else:
            info_hash = item["infoHash"]
        return info_hash

    def parse_stream_title(self, item: Dict[str, Any]) -> Dict[str, Any]:
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

    def extract_size_string(self, details: str) -> str:
        size_match = re.search(r"💾 (\d+(?:\.\d+)?\s*(GB|MB))", details, re.IGNORECASE)
        return size_match.group(1) if size_match else ""

    def extract_seeders(self, details: str) -> int:
        seeders_match = re.search(r"👤 (\d+)", details)
        return int(seeders_match.group(1)) if seeders_match else 0
