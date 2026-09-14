"""Anime identity resolution across AniList, Simkl and AniZip."""

from datetime import timedelta
from typing import Any, Dict, Optional, Tuple

from lib.anime.normalize import AnimeRecord, record_from_payloads
from lib.db.cached import MemoryCache
from lib.utils.kodi.logging import kodilog

CACHE_TTL = timedelta(hours=24)

_CACHE = MemoryCache(database="jacktook.anime.identity")

_SIMKL_PROVIDER_MAP: Tuple[Tuple[str, str], ...] = (
    # tvdb/imdb are unambiguous; tmdb needs the type hint, so it goes last.
    ("tvdb_id", "tvdb"),
    ("imdb_id", "imdb"),
    ("mal_id", "mal"),
    ("anilist_id", "anilist"),
    ("tmdb_id", "tmdb"),
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

        media_type = _seed_media_type(source)

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
        # Also try Simkl when the seed had an AniList/MAL source but the initial
        # AniList fetch failed: Simkl may still carry the title.
        if simkl_payload is None and (not _has_anilist_source(source) or anilist_payload is None):
            provider, value = _pick_simkl_provider(resolved)
            if provider is not None:
                if media_type:
                    simkl_payload = simkl.resolve_ids(provider, value, media_type=media_type)
                else:
                    simkl_payload = simkl.resolve_ids(provider, value)
                # ``resolve_ids`` only carries ids; fetch the detail entry so
                # titles are available without a later AniList round-trip.
                if not _simkl_has_title(simkl_payload):
                    _merge_ids(resolved, _simkl_payload_ids(simkl_payload))
                    if resolved.get("simkl_id") is not None:
                        detail = simkl.anime_detail(resolved["simkl_id"])
                        if detail is not None:
                            simkl_payload = detail
        _merge_ids(resolved, _simkl_payload_ids(simkl_payload))

        anizip_payload: Optional[Dict[str, Any]] = None
        anilist_id = resolved.get("anilist_id")
        mal_id = resolved.get("mal_id")
        if (anilist_id is not None or mal_id is not None) and not _simkl_covers_anizip(
            simkl_payload
        ):
            anizip_payload = anizip.mappings(anilist_id=anilist_id, mal_id=mal_id)
        _merge_ids(resolved, _anizip_ids(anizip_payload))

        # Simkl titles are sufficient for the menu; only pay for AniList when
        # Simkl had no usable title (or the seed already required AniList).
        if anilist_payload is None and not _simkl_has_title(simkl_payload):
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
        if _has_usable_title(record):
            _CACHE.set(cache_key, record, expires=CACHE_TTL)
        return record
    except Exception as error:
        kodilog(f"anime identity resolution failed: {error}")
        return None


def _has_usable_title(record: AnimeRecord) -> bool:
    """Return True when the record carries at least one non-empty title.

    A record without titles only holds seed ids: caching it would pin a
    degraded result for the whole TTL and prevent provider retries.
    """
    return bool(
        record.title_en or record.title_romaji or record.title_native or record.title_default
    )


def _has_anilist_source(source: Dict[str, Any]) -> bool:
    return source.get("anilist_id") is not None or source.get("mal_id") is not None


def _seed_media_type(source: Dict[str, Any]) -> Optional[str]:
    """Return the optional ``media_type``/``type`` hint from a seed dict.

    Only ``tv`` and ``movie`` are recognized; anything else degrades to None so
    the Simkl lookup keeps its untyped behavior.
    """
    value = source.get("media_type")
    if value is None:
        value = source.get("type")
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ("tv", "movie"):
            return normalized
    return None


def _simkl_has_title(payload: Optional[Dict[str, Any]]) -> bool:
    """Return True when the Simkl payload carries a usable title."""
    if not isinstance(payload, dict):
        return False
    for key in ("en_title", "romaji", "title"):
        value = payload.get(key)
        if value is not None and str(value).strip():
            return True
    return False


def _simkl_covers_anizip(payload: Optional[Dict[str, Any]]) -> bool:
    """Return True when Simkl already carries every id AniZip would provide.

    AniZip only adds anilist/mal/tvdb/tmdb/imdb ids (its episode map is not
    consumed by the normalizer). When Simkl supplied all of them, the extra
    AniZip request is redundant and can be skipped safely.
    """
    if not isinstance(payload, dict):
        return False
    nested = payload.get("ids")
    ids = nested if isinstance(nested, dict) else payload
    field_pairs: Tuple[Tuple[str, ...], ...] = (
        ("anilist", "anilist_id"),
        ("mal", "mal_id"),
        ("tvdb", "tvdb_id"),
        ("tmdb", "tmdb_id"),
        ("imdb", "imdb_id"),
    )
    for keys in field_pairs:
        value = None
        for key in keys:
            candidate = ids.get(key)
            if candidate is not None and candidate != "":
                value = candidate
                break
        if value is None:
            return False
    return True


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
