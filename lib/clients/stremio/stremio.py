from lib.clients.stremio.addons_manager import Addon
from lib.clients.stremio.stream import Stream
from lib.clients.base import BaseClient, TorrentStream

from lib.utils.debrid.debrid_utils import process_external_cache
from lib.utils.general.utils import USER_AGENT_HEADER, IndexerType, info_hash_to_magnet
from lib.utils.kodi.utils import convert_size_to_bytes, get_setting, kodilog
from lib.utils.localization.language_detection import find_languages_in_string

from lib.db.cached import cache

import re
from typing import List, Dict, Optional, Any


TORRENTIO_PROVIDERS_KEY = "torrentio.providers"

EXCLUDED_RD_ADDONS = ["org.nuvio.streams", "org.mycine.addon"]


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

    def parse_response(self, res: Any) -> List[TorrentStream]:
        return []

    def search_catalog(self, query: str) -> List[TorrentStream]:
        return []

    def get_catalog_info(self, skip: Optional[int]) -> Optional[Dict[str, Any]]:
        if skip:
            skip_append = f"/skip={skip}.json"
        else:
            skip_append = ".json"
        url = f"{self.base_url}/catalog/{self.params['catalog_type']}/{self.params['catalog_id']}{skip_append}"
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
            else:
                return []

            kodilog("Using Stremio addon search URL: " + url)

            if self.should_use_rd_cache():
                return self.get_rd_cached_results(imdb_id, mode, season, episode)

            if get_setting("torrentio_enabled") and "torrentio" in self.addon.url():
                providers = cache.get(TORRENTIO_PROVIDERS_KEY)
                if providers:
                    url = url.replace("/stream/", f"/providers={providers}/stream/")
                    kodilog(f"URL with providers: {url}")

            res = self.session.get(url, headers=USER_AGENT_HEADER, timeout=10)
            if res.status_code != 200:
                return []
            return self.parse_response(res)
        except Exception as e:
            self.handle_exception(f"Error in {self.addon.manifest.name}: {str(e)}")
            return []

    def parse_response(self, res: Any, is_cached: bool = False) -> List[TorrentStream]:
        res = res.json()
        results = []

        for item in res["streams"]:
            stream = Stream(item)
            parsed = self.parse_torrent_description(stream.description)

            if is_cached:
                match = re.search(r"\b\w{40}\b", stream.url)
                info_hash = match.group() if match else item.get("infoHash")
                url = ""
            else:
                info_hash = stream.infoHash
                url = stream.url

            results.append(
                TorrentStream(
                    title=stream.get_parsed_title(),
                    type=(IndexerType.STREMIO_DEBRID if url else IndexerType.TORRENT),
                    indexer=self.addon.manifest.name.split(" ")[0],
                    guid=info_hash_to_magnet(info_hash),
                    infoHash=info_hash,
                    size=stream.get_parsed_size()
                    or item.get("sizebytes")
                    or parsed["size"],
                    seeders=item.get("seed", 0) or parsed["seeders"],
                    languages=parsed["languages"],
                    fullLanguages=parsed["languages"],
                    provider=parsed["provider"],
                    publishDate="",
                    peers=0,
                    url=url,
                    isCached=is_cached,
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

    def should_use_rd_cache(self) -> Optional[bool]:
        """Checks if RD cache should be used for this addon."""
        return (
            get_setting("real_debrid_enabled")
            and get_setting("real_debrid_cached_check")
            and not get_setting("torrent_enable")
            and not get_setting("stremio_loggedin")
            and self.addon.manifest.id not in EXCLUDED_RD_ADDONS
        )

    def get_rd_cached_results(
        self,
        imdb_id: str,
        mode: str,
        season: Optional[int],
        episode: Optional[int],
    ) -> List[TorrentStream]:
        """Fetches and parses Real-Debrid cached results."""
        kodilog("Using Real-Debrid cached results")
        cached_results = process_external_cache(
            data={
                "imdb_id": imdb_id,
                "season": season,
                "episode": episode,
                "mode": mode,
            },
            debrid="realdebrid",
            token=str(get_setting("real_debrid_token")),
            url=self.addon.url(),
        )
        if not cached_results:
            return []
        return self.parse_response(cached_results, is_cached=True)
