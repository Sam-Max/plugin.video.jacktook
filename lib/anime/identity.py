"""Anime identity resolution across AniList, Simkl and AniZip."""

from datetime import timedelta
from typing import Any, Dict, Optional, Tuple

from lib.anime.normalize import AnimeRecord, record_from_payloads
from lib.db.cached import MemoryCache
from lib.utils.kodi.logging import kodilog

CACHE_TTL = timedelta(hours=24)

_CACHE = MemoryCache(database="jacktook.anime.identity")

_SIMKL_PROVIDER_MAP: Tuple[Tuple[str, str], ...] = (
    ("tmdb_id", "tmdb"),
    ("tvdb_id", "tvdb"),
    ("imdb_id", "imdb"),
    ("mal_id", "mal"),
    ("anilist_id", "anilist"),
)


def resolve_identity(ids: Optional[Dict[str, Any]]) -> Optional[AnimeRecord]:
    """Resolve a canonical AnimeRecord from any known external ids.

    Each provider step is optional: a failure degrades to a partial record
    instead of raising.
    """
    try:
        source = _as_dict(ids)
        if not source:
            return None

        cache_key = _cache_key(source)
        cached = _CACHE.get(cache_key)
        if isinstance(cached, AnimeRecord):
            return cached

        from lib.anime.providers import anilist, anizip, simkl

        anilist_payload: Optional[Dict[str, Any]] = None
        if source.get("anilist_id") is not None:
            anilist_payload = anilist.fetch_by_anilist_id(source["anilist_id"])
        elif source.get("mal_id") is not None:
            anilist_payload = anilist.fetch_by_mal_id(source["mal_id"])

        resolved = dict(source)
        _merge_ids(resolved, _anilist_ids(anilist_payload))

        simkl_payload: Optional[Dict[str, Any]] = None
        if source.get("simkl_id") is not None:
            simkl_payload = simkl.anime_detail(source["simkl_id"])
        if simkl_payload is None and not _has_anilist_source(source):
            provider, value = _pick_simkl_provider(resolved)
            if provider is not None:
                simkl_payload = simkl.resolve_ids(provider, value)
        _merge_ids(resolved, _simkl_payload_ids(simkl_payload))

        anizip_payload: Optional[Dict[str, Any]] = None
        anilist_id = resolved.get("anilist_id")
        mal_id = resolved.get("mal_id")
        if anilist_id is not None or mal_id is not None:
            anizip_payload = anizip.mappings(anilist_id=anilist_id, mal_id=mal_id)
        _merge_ids(resolved, _anizip_ids(anizip_payload))

        if anilist_payload is None:
            if resolved.get("anilist_id") is not None:
                anilist_payload = anilist.fetch_by_anilist_id(resolved["anilist_id"])
            elif resolved.get("mal_id") is not None:
                anilist_payload = anilist.fetch_by_mal_id(resolved["mal_id"])

        record = record_from_payloads(
            anilist=anilist_payload,
            simkl=simkl_payload,
            anizip=anizip_payload,
            seed=resolved,
        )
        _CACHE.set(cache_key, record, expires=CACHE_TTL)
        return record
    except Exception as error:
        kodilog(f"anime identity resolution failed: {error}")
        return None


def _has_anilist_source(source: Dict[str, Any]) -> bool:
    return source.get("anilist_id") is not None or source.get("mal_id") is not None


def _pick_simkl_provider(resolved: Dict[str, Any]) -> Tuple[Optional[str], Any]:
    for key, provider in _SIMKL_PROVIDER_MAP:
        value = resolved.get(key)
        if value is not None and value != "":
            return provider, value
    return None, None


def _anilist_ids(payload: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return None
    result: Dict[str, Any] = {}
    if payload.get("id") is not None:
        result["anilist_id"] = payload["id"]
    if payload.get("idMal") is not None:
        result["mal_id"] = payload["idMal"]
    return result


def _simkl_payload_ids(payload: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return None
    nested = payload.get("ids")
    ids = nested if isinstance(nested, dict) else payload
    field_map: Tuple[Tuple[str, str], ...] = (
        ("simkl", "simkl_id"),
        ("mal", "mal_id"),
        ("anilist", "anilist_id"),
        ("anidb", "anidb_id"),
        ("kitsu", "kitsu_id"),
        ("tmdb", "tmdb_id"),
        ("tvdb", "tvdb_id"),
        ("imdb", "imdb_id"),
    )
    result: Dict[str, Any] = {}
    for source_key, target_key in field_map:
        value = ids.get(source_key)
        if value is not None and value != "":
            result[target_key] = value
    return result


def _anizip_ids(payload: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return None
    field_map: Tuple[Tuple[str, str], ...] = (
        ("anilist_id", "anilist_id"),
        ("mal_id", "mal_id"),
        ("tvdb_id", "tvdb_id"),
        ("thetvdb_id", "tvdb_id"),
        ("imdb_id", "imdb_id"),
        ("tmdb_id", "tmdb_id"),
    )
    result: Dict[str, Any] = {}
    for source_key, target_key in field_map:
        value = payload.get(source_key)
        if value is not None and value != "" and target_key not in result:
            result[target_key] = value
    return result


def _merge_ids(target: Dict[str, Any], extra: Optional[Dict[str, Any]]) -> None:
    if not isinstance(extra, dict):
        return
    for key, value in extra.items():
        if value is None or value == "":
            continue
        if target.get(key) is None:
            target[key] = value


def _cache_key(source: Dict[str, Any]) -> str:
    parts = [f"{key}={source[key]}" for key in sorted(source) if source[key] is not None]
    return "anime_identity::" + "|".join(parts)


def _as_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}
