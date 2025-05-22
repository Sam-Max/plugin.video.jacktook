from lib.clients.stremio.addons_manager import Addon
from lib.clients.stremio.stream import Stream
from lib.clients.base import BaseClient, TorrentStream
from lib.utils.general.utils import USER_AGENT_HEADER, IndexerType, info_hash_to_magnet
from lib.utils.kodi.utils import convert_size_to_bytes, kodilog
from lib.utils.localization.language_detection import find_languages_in_string

import re
from typing import List, Dict, Optional, Any


class StremioAddonCatalogsClient(BaseClient):
    def __init__(self, params: Dict[str, Any]) -> None:
        super().__init__(None, None)
        self.params = params
        self.base_url = self.params["addon_url"]

    def search(
        self,
        imdb_id: str,
        mode: str,
        media_type: str,
        season: Optional[int],
        episode: Optional[int],
        dialog: Any,
    ) -> None:
        pass

    def parse_response(self, res: any) -> None:
        pass

    def get_catalog_info(self, skip: int) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/catalog/{self.params['catalog_type']}/{self.params['catalog_id']}/skip={skip}.json"
        res = self.session.get(url, headers=USER_AGENT_HEADER, timeout=10)
        if res.status_code != 200:
            return
        return res.json()

    def get_meta_info(self) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/meta/{self.params['catalog_type']}/{self.params['video_id']}.json"
        res = self.session.get(url, headers=USER_AGENT_HEADER, timeout=10)
        if res.status_code != 200:
            return
        return res.json()

    def get_stream_info(self) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/stream/{self.params['catalog_type']}/{self.params['video_id']}.json"
        res = self.session.get(url, headers=USER_AGENT_HEADER, timeout=10)
        if res.status_code != 200:
            return
        return res.json()


class StremioAddonClient(BaseClient):
    def __init__(self, addon: Addon) -> None:
        super().__init__(None, None)
        self.addon = addon

    def search(
        self,
        imdb_id: str,
        mode: str,
        media_type: str,
        season: Optional[int],
        episode: Optional[int],
    ) -> List[TorrentStream]:
        try:
            kodilog(f"Searching for {imdb_id} on {self.addon.manifest.name}")
            
            if mode == "tv" or media_type == "tv":
                if not self.addon.isSupported("stream", "series", "tt"):
                    return []
                url = f"{self.addon.url()}/stream/series/{imdb_id}:{season}:{episode}.json"
            elif mode == "movies" or media_type == "movies":
                if not self.addon.isSupported("stream", "movie", "tt"):
                    return []
                url = f"{self.addon.url()}/stream/movie/{imdb_id}.json"

            kodilog(f"URL: {url}")
            
            res = self.session.get(url, headers=USER_AGENT_HEADER, timeout=10)
            if res.status_code != 200:
                return []
            return self.parse_response(res)
        except Exception as e:
            self.handle_exception(f"Error in {self.addon.manifest.name}: {str(e)}")

    def parse_response(self, res: any) -> List[TorrentStream]:
        res = res.json()
        results = []
        for item in res["streams"]:
            stream = Stream(item)
            parsed = self.parse_torrent_description(stream.description)
            results.append(
                TorrentStream(
                    title=stream.get_parsed_title(),
                    type=(
                        IndexerType.STREMIO_DEBRID
                        if stream.url
                        else IndexerType.TORRENT
                    ),
                    indexer=self.addon.manifest.name.split(" ")[0],
                    guid=info_hash_to_magnet(stream.infoHash),
                    infoHash=stream.infoHash,
                    size=stream.get_parsed_size()
                    or item.get("sizebytes")
                    or parsed["size"],
                    seeders=item.get("seed", 0) or parsed["seeders"],
                    languages=parsed["languages"],
                    fullLanguages=parsed["languages"],
                    provider=parsed["provider"],
                    publishDate="",
                    peers=0,
                )
            )
        return results

    def parse_torrent_description(self, desc: str) -> Dict[str, Any]:
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
