from lib.api.stremio.addon_manager import Addon
from lib.api.stremio.models import Stream, Meta, MetaPreview
from lib.clients.base import BaseClient, TorrentStream

from lib.utils.debrid.debrid_utils import process_external_cache
from lib.utils.general.utils import USER_AGENT_HEADER, IndexerType, info_hash_to_magnet
from lib.utils.kodi.settings import get_int_setting
from lib.utils.kodi.utils import convert_size_to_bytes, get_setting, kodilog
from lib.utils.localization.language_detection import find_languages_in_string

from lib.db.cached import cache

import re
from typing import List, Dict, Optional, Any


from lib.clients.stremio.constants import TORRENTIO_PROVIDERS_KEY

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

    def search_catalog(self, query: str) -> Optional[Dict[str, Any]]:
        return self.get_catalog_info(search=query)

    def get_catalog_info(self, **kwargs) -> Optional[Dict[str, Any]]:
        extra_path = ""
        for key, value in kwargs.items():
            if value:
                extra_path += f"/{key}={value}"

        if not extra_path:
            path_suffix = ".json"
        else:
            path_suffix = f"{extra_path}.json"

        url = f"{self.base_url}/catalog/{self.params['catalog_type']}/{self.params['catalog_id']}{path_suffix}"
        res = self.session.get(url, headers=USER_AGENT_HEADER, timeout=10)
        if res.status_code != 200:
            return

        data = res.json()
        if "metas" in data:
            data["metas"] = [MetaPreview.from_dict(m) for m in data["metas"]]
        return data

    def get_meta_info(self) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/meta/{self.params['catalog_type']}/{self.params['meta_id']}.json"
        res = self.session.get(url, headers=USER_AGENT_HEADER, timeout=10)
        if res.status_code != 200:
            return

        data = res.json()
        if "meta" in data:
            data["meta"] = Meta.from_dict(data["meta"])
        return data

    def get_stream_info(self) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/stream/{self.params['catalog_type']}/{self.params['meta_id']}.json"
        res = self.session.get(url, headers=USER_AGENT_HEADER, timeout=10)
        if res.status_code != 200:
            return

        data = res.json()
        if "streams" in data:
            data["streams"] = [Stream.from_dict(s) for s in data["streams"]]
        return data


class StremioAddonClient(BaseClient):
    def __init__(self, addon: Addon) -> None:
        super().__init__(None, None)
        self.addon = addon

    def search(
        self,
        video_id: str,
        mode: str,
        media_type: str,
        season: Optional[int],
        episode: Optional[int],
    ) -> List[TorrentStream]:
        try:
            prefix = video_id.split(":")[0] if ":" in video_id else "tt"

            if mode == "tv" or media_type == "tv":
                if not self.addon.isSupported("stream", "series", prefix):
                    return []

                if prefix == "kitsu":
                    url = f"{self.addon.url()}/stream/series/{video_id}:{episode}.json"
                else:
                    url = f"{self.addon.url()}/stream/series/{video_id}:{season}:{episode}.json"
            elif mode == "movies" or media_type == "movies":
                if not self.addon.isSupported("stream", "movie", prefix):
                    return []
                url = f"{self.addon.url()}/stream/movie/{video_id}.json"
            else:
                return []

            kodilog("Using Stremio addon search URL: " + url)

            if get_setting("torrentio_enabled") and "torrentio" in self.addon.url():
                if "/providers=" not in url:
                    providers = cache.get(TORRENTIO_PROVIDERS_KEY)
                    if providers:
                        url = url.replace("/stream/", f"/providers={providers}/stream/")
                        kodilog(f"URL with providers: {url}")

            res = self.session.get(
                url,
                headers=USER_AGENT_HEADER,
                timeout=get_int_setting("stremio_timeout"),
            )
            if res.status_code != 200:
                return []
            response = self.parse_response(res)
            kodilog(
                f"Stremio addon {self.addon.manifest.name} returned {len(response)} results"
            )
            return response
        except Exception as e:
            self.handle_exception(f"Error in {self.addon.manifest.name}: {str(e)}")
            return []

    def parse_response(
        self, res: Any, is_external_cache: bool = False
    ) -> List[TorrentStream]:
        if not is_external_cache:
            res_json = res.json()
            streams = res_json.get("streams", [])
        else:
            pass

        if hasattr(res, "json"):
            data = res.json()
        elif isinstance(res, dict):
            data = res
        else:
            data = {}

        results = []

        streams = data.get("streams", [])

        for item in streams:
            stream = Stream.from_dict(item)
            parsed = self.parse_torrent_description(
                stream.description or stream.title or ""
            )

            if is_external_cache:
                match = re.search(r"\b\w{40}\b", stream.url or "")
                info_hash = match.group() if match else item.get("infoHash")
                url = ""
                is_cached = True
            else:
                info_hash = stream.infoHash
                url = stream.url
                is_cached = True if url else False

            results.append(
                TorrentStream(
                    title=stream.get_parsed_title(),
                    type=(IndexerType.STREMIO_DEBRID if url else IndexerType.TORRENT),
                    indexer=self.addon.manifest.name.split(" ")[0],
                    subindexer=stream.get_sub_indexer(self.addon),
                    guid=info_hash_to_magnet(info_hash) if info_hash else "",
                    infoHash=info_hash,
                    size=stream.get_parsed_size()
                    or item.get("sizebytes")
                    or parsed["size"],
                    seeders=item.get("seed", 0) or parsed["seeders"],
                    languages=parsed["languages"],
                    fullLanguages=parsed["languages"],
                    provider=stream.get_provider() or parsed["provider"],
                    publishDate="",
                    peers=0,
                    url=url,
                    isCached=is_cached,
                )
            )
        return results

    def parse_torrent_description(self, desc: str) -> Dict[str, Any]:
        if not desc:
            return {
                "size": 0,
                "seeders": 0,
                "provider": "",
                "languages": [],
            }
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

    def should_use_ad_cache(self) -> Optional[bool]:
        """Checks if RD cache should be used for this addon."""
        return (
            get_setting("alldebrid_enabled")
            and get_setting("alldebrid_cached_check")
            and not get_setting("torrent_enable")
            and not get_setting("stremio_loggedin")
            and self.addon.manifest.id not in EXCLUDED_RD_ADDONS
        )

    def get_cached_results(
        self,
        imdb_id: str,
        mode: str,
        season: Optional[int],
        episode: Optional[int],
        debridType="",
        debridToken="",
    ) -> List[TorrentStream]:
        cached_results = process_external_cache(
            data={
                "imdb_id": imdb_id,
                "season": season,
                "episode": episode,
                "mode": mode,
            },
            debrid=debridType,
            token=str(debridToken),
            url=self.addon.url(),
        )
        if not cached_results:
            return []
        return self.parse_response(cached_results, is_external_cache=True)
