import re
from typing import Any, Dict, List, Mapping, Optional
from urllib.parse import quote

import xbmc

from lib.api.stremio.addon_manager import Addon, build_addon_instance_label
from lib.api.stremio.models import Meta, MetaPreview, Stream
from lib.clients.base import BaseClient, TorrentStream
from lib.clients.stremio.helpers import get_addon_display_name
from lib.clients.stremio.playback import classify, normalize_stream
from lib.utils.debrid.debrid_utils import process_external_cache
from lib.utils.general.utils import USER_AGENT_HEADER, IndexerType, info_hash_to_magnet
from lib.utils.kodi.settings import get_int_setting
from lib.utils.kodi.utils import convert_size_to_bytes, get_setting, kodilog
from lib.utils.localization.language_detection import find_languages_in_string

EXCLUDED_RD_ADDONS = ["org.nuvio.streams", "org.mycine.addon"]


def _candidate_metadata(candidate, url_override=None, info_hash_override=None):
    metadata = dict(candidate.metadata)
    metadata.update(
        {
            "url": candidate.url if url_override is None else url_override,
            "ytId": candidate.ytId,
            "infoHash": candidate.infoHash
            if info_hash_override is None
            else info_hash_override,
            "fileIdx": candidate.fileIdx,
            "externalUrl": candidate.externalUrl,
            "title": candidate.title,
            "name": candidate.name,
            "description": candidate.description,
            "filename": candidate.filename,
            "size": candidate.size,
            "videoHash": candidate.videoHash,
            "subtitles": list(candidate.subtitles),
            "sources": list(candidate.sources),
            "trackers": list(candidate.trackers),
            "fileMustInclude": candidate.fileMustInclude,
            "nzbUrl": candidate.nzbUrl,
        }
    )

    behavior_hints = {}
    if candidate.filename is not None:
        behavior_hints["filename"] = candidate.filename
    if candidate.size is not None:
        behavior_hints["videoSize"] = candidate.size
    if candidate.videoHash is not None:
        behavior_hints["videoHash"] = candidate.videoHash
    if candidate.headers or candidate.responseHeaders:
        behavior_hints["proxyHeaders"] = {
            "request": dict(candidate.headers),
            "response": dict(candidate.responseHeaders),
        }
    if behavior_hints:
        metadata["behaviorHints"] = behavior_hints

    return metadata


def _response_data(response):
    try:
        if hasattr(response, "json"):
            data = response.json()
        elif isinstance(response, Mapping):
            data = response
        else:
            return {}
    except Exception:
        return {}
    return data if isinstance(data, Mapping) else {}


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
        extra_path = "".join(
            f"/{key}={quote(str(value), safe='')}"
            for key, value in kwargs.items()
            if value is not None and value != ""
        )

        if not extra_path:
            path_suffix = ".json"
        else:
            path_suffix = f"{extra_path}.json"

        catalog_type = self.params.get("catalog_type")
        catalog_id = self.params.get("catalog_id")
        url = f"{self.base_url}/catalog/{catalog_type}/{catalog_id}{path_suffix}"

        kodilog(f"Using Stremio addon catalog URL: {url}")

        res = self.session.get(
            url, headers=USER_AGENT_HEADER, timeout=get_int_setting("stremio_timeout")
        )
        if res.status_code != 200:
            return

        data = res.json()
        if "metas" in data:
            data["metas"] = [MetaPreview.from_dict(m) for m in data["metas"]]
        return data

    def get_meta_info(self) -> Optional[Dict[str, Any]]:
        catalog_type = self.params.get("catalog_type")
        meta_id = self.params.get("meta_id")
        url = f"{self.base_url}/meta/{catalog_type}/{meta_id}.json"

        kodilog(f"Using Stremio addon meta URL: {url}")

        res = self.session.get(
            url, headers=USER_AGENT_HEADER, timeout=get_int_setting("stremio_timeout")
        )
        if res.status_code != 200:
            return

        data = res.json()
        if "meta" in data:
            data["meta"] = Meta.from_dict(data["meta"])
        return data

    def get_stream_info(self) -> Optional[Dict[str, Any]]:
        catalog_type = self.params.get("catalog_type")
        meta_id = self.params.get("meta_id")
        url = f"{self.base_url}/stream/{catalog_type}/{meta_id}.json"

        kodilog(f"Using Stremio addon stream URL: {url}")

        res = self.session.get(
            url, headers=USER_AGENT_HEADER, timeout=get_int_setting("stremio_timeout")
        )
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
        self.display_name = get_addon_display_name(addon)
        self.instance_label = build_addon_instance_label(
            {
                "manifest": {"id": addon.manifest.id, "name": self.display_name},
                "transportUrl": addon.transport_url,
                "transportName": addon.transport_name,
            }
        )
        self.indexer_name = (addon.manifest.name or addon.manifest.id).split(" ")[0]

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

            res = self.session.get(
                url,
                headers=USER_AGENT_HEADER,
                timeout=get_int_setting("stremio_timeout"),
            )
            if res.status_code != 200:
                return []
            response = self.parse_response(res)
            kodilog(f"Stremio addon {self.display_name} returned {len(response)} results")
            return response
        except Exception:
            self.handle_exception(f"Error in {self.display_name}")
            return []

    def parse_response(self, res: Any, is_external_cache: bool = False) -> List[TorrentStream]:
        data = _response_data(res)
        streams = data.get("streams", [])
        if not isinstance(streams, (list, tuple)):
            return []
        results = []

        for item in streams:
            try:
                candidate = normalize_stream(
                    item, origin="external_cache" if is_external_cache else "search"
                )
            except (TypeError, ValueError):
                continue

            item_values = dict(item) if isinstance(item, Mapping) else {}
            parsed = self.parse_torrent_description(
                candidate.description or candidate.title or ""
            )

            if is_external_cache:
                match = re.search(r"\b[0-9a-fA-F]{40}\b", candidate.url or "")
                info_hash = (
                    candidate.infoHash
                    or (match.group() if match else None)
                    or item_values.get("infoHash")
                )
                url = ""
                is_cached = True
            else:
                info_hash = candidate.infoHash
                url = candidate.url or ""
                is_cached = bool(url)

            decision = classify(candidate)
            if decision.code in {
                "external_source",
                "unsupported_archive",
                "malformed_locator",
                "unsafe_locator",
                "response_headers_unsupported",
                "unsafe_headers",
                "unsupported_source",
            }:
                continue

            stream_type = IndexerType.STREMIO_DEBRID if url else IndexerType.TORRENT
            raw_meta = candidate.metadata.get("meta", {})
            stream_provider = (
                raw_meta.get("indexer", "") if isinstance(raw_meta, Mapping) else ""
            ) or parsed["provider"]
            name_parts = (candidate.name or "").split()
            stream_subindexer = name_parts[1] if len(name_parts) > 1 else ""
            stream_size = candidate.size or item_values.get("sizebytes") or parsed["size"]
            stream_seeders = item_values.get("seed", 0) or parsed["seeders"]
            stream_subtitles = [subtitle for subtitle in candidate.subtitles if subtitle.get("url")]
            if stream_subtitles:
                kodilog(
                    f"[StremioSubs] {self.display_name}: stream "
                    f"'{(candidate.title or candidate.name or '')[:40]}' has "
                    f"{len(stream_subtitles)} embedded subtitle(s)",
                    level=xbmc.LOGINFO,
                )

            title = candidate.filename or candidate.description or candidate.title or ""
            results.append(
                TorrentStream(
                    title=title.splitlines()[0] if title else "",
                    type=stream_type,
                    indexer=self.indexer_name,
                    subindexer=stream_subindexer,
                    addonKey=self.addon.key(),
                    addonName=self.display_name,
                    addonSourceName=self.addon.manifest.name or self.addon.manifest.id,
                    addonInstanceLabel=self.instance_label,
                    guid=info_hash_to_magnet(info_hash) if info_hash else "",
                    infoHash=info_hash if info_hash else "",
                    size=stream_size,
                    seeders=stream_seeders,
                    languages=parsed["languages"],
                    fullLanguages=parsed["languages"],
                    provider=stream_provider,
                    publishDate="",
                    peers=0,
                    url=url if url else "",
                    streamSubtitles=stream_subtitles,
                    isCached=is_cached,
                    stremioMetadata=_candidate_metadata(
                        candidate,
                        url_override=url if is_external_cache else None,
                        info_hash_override=info_hash if is_external_cache else None,
                    ),
                )
            )

        streams_with_subs = sum(1 for r in results if r.streamSubtitles)
        if streams_with_subs:
            kodilog(
                f"[StremioSubs] {self.display_name}: {streams_with_subs}/{len(results)} "
                f"streams carry embedded subtitles",
                level=xbmc.LOGINFO,
            )
        else:
            kodilog(
                f"[StremioSubs] {self.display_name}: no embedded subtitles in any of "
                f"{len(results)} streams",
                level=xbmc.LOGINFO,
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
        size_pattern = r"💾 ([\d.,]+ (?:GB|MB|Go|Mo))"
        size_match = re.search(size_pattern, desc, re.IGNORECASE)
        size = size_match.group(1) if size_match else None
        if size:
            size = convert_size_to_bytes(size)

        # Extract seeders
        seeders_pattern = r"[👥👤] (\d+)"
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

    def should_use_rd_cache(self) -> bool:
        """Checks if RD cache should be used for this addon."""
        return bool(
            get_setting("real_debrid_enabled")
            and get_setting("real_debrid_cached_check")
            and not get_setting("torrent_enable")
            and not get_setting("stremio_loggedin")
            and self.addon.manifest.id not in EXCLUDED_RD_ADDONS
        )

    def should_use_ad_cache(self) -> bool:
        """Checks if AD cache should be used for this addon."""
        return bool(
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
