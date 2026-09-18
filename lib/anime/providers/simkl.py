"""Simkl public client used to resolve external anime ids."""

from datetime import timedelta
from typing import Any, Dict, List, Optional

import requests

from lib.db.cached import MemoryCache
from lib.utils.kodi.logging import kodilog

SIMKL_CLIENT_ID = "59dfdc579d244e1edf6f89874d521d37a69a95a1abd349910cb056a1872ba2c8"
SIMKL_BASE_URL = "https://api.simkl.com"
USER_AGENT = "jacktook-anime/1.0"
CACHE_TTL = timedelta(hours=24)

_CACHE = MemoryCache(database="jacktook.anime.simkl")


def resolve_ids(
    provider: str, value: Any, media_type: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Resolve a normalized id block for a provider/value pair.

    When ``provider`` is ``tmdb`` and ``media_type`` is ``tv`` or ``movie`` the
    lookup is disambiguated with Simkl's ``type`` parameter: a TMDB series id
    can collide with a movie that shares the same numeric id.
    """
    if not provider or value is None:
        return None
    key = f"simkl:search:{provider}:{value}"
    if media_type:
        # Keep tv/movie resolutions in separate cache entries.
        key = f"{key}:{media_type}"
    cached = _CACHE.get(key)
    if isinstance(cached, dict):
        return cached
    params = {provider: value, "client_id": SIMKL_CLIENT_ID}
    if provider == "tmdb" and media_type in ("tv", "movie"):
        params["type"] = media_type
    data = _request("search/id", params)
    ids = _extract_ids(data)
    if ids is None:
        return None
    result = {
        "simkl": _to_int(ids.get("simkl")),
        "mal": _to_int(ids.get("mal")),
        "anilist": _to_int(ids.get("anilist")),
        "anidb": _to_int(ids.get("anidb")),
        "kitsu": _to_int(ids.get("kitsu")),
        "tmdb": _to_int(ids.get("tmdb")),
        "tvdb": _to_int(ids.get("tvdb")),
        "imdb": _to_str(ids.get("imdb")),
    }
    _CACHE.set(key, result, expires=CACHE_TTL)
    return result


def anime_detail(simkl_id: Any) -> Optional[Dict[str, Any]]:
    """Fetch and normalize a Simkl anime entry.

    Returns a shape consumed by ``record_from_payloads`` (nested ``ids`` plus
    the romaji/english titles) or ``None`` on any failure.
    """
    if simkl_id is None:
        return None
    key = f"simkl:anime:{simkl_id}"
    cached = _CACHE.get(key)
    if isinstance(cached, dict):
        return cached
    params = {"extended": "full", "client_id": SIMKL_CLIENT_ID}
    data = _request(f"anime/{simkl_id}", params)
    result = _normalize_detail(data)
    if result is None:
        return None
    _CACHE.set(key, result, expires=CACHE_TTL)
    return result


def _normalize_detail(data: Any) -> Optional[Dict[str, Any]]:
    """Normalize a Simkl anime detail payload into the shared record shape.

    Returns ``None`` for a payload with neither a usable title nor any ids so
    an empty HTTP-200 body is never cached as an all-``None`` detail.
    """
    if not isinstance(data, dict):
        return None
    ids = data.get("ids")
    if not isinstance(ids, dict):
        ids = {}
    title = _to_str(data.get("title"))
    en_title = _to_str(data.get("en_title"))
    has_ids = any(value is not None and value != "" for value in ids.values())
    if not title and not en_title and not has_ids:
        return None
    return {
        "ids": ids,
        "en_title": en_title,
        "romaji": title,
        "title": title,
        "overview": _to_str(data.get("overview")),
        "year": _to_int(data.get("year")),
        "episodes": _to_int(data.get("total_episodes")),
    }


def fetch_entry(simkl_id: Any) -> Optional[Dict[str, Any]]:
    """Fetch the per-cour identity fields of one Simkl anime entry.

    Simkl carries one entry per cour of a multi-cour anime. Besides the id
    block, each entry publishes the seasons it covers (``mapped_tvdb_seasons``)
    and the ``sequel`` relations needed to walk to the entry covering another
    season. The normalized shape is consumed by
    :func:`lib.anime.season_entry.resolve_season_entry`; ``None`` is returned
    on any network or shape failure. Failed parses are not cached so a later
    playback attempt can retry.
    """
    if simkl_id is None:
        return None
    key = f"simkl:entry:{simkl_id}"
    cached = _CACHE.get(key)
    if isinstance(cached, dict):
        return cached
    params = {"extended": "full", "client_id": SIMKL_CLIENT_ID}
    data = _request(f"anime/{simkl_id}", params)
    result = _normalize_entry(data)
    if result is None:
        return None
    _CACHE.set(key, result, expires=CACHE_TTL)
    return result


def _normalize_entry(data: Any) -> Optional[Dict[str, Any]]:
    """Normalize a Simkl detail payload into the per-cour entry shape.

    Returns ``None`` unless the payload carries a usable ``ids`` block: without
    ids the entry can neither route playback nor anchor the sequel walk.
    """
    if not isinstance(data, dict):
        return None
    ids = data.get("ids")
    if not isinstance(ids, dict):
        return None
    simkl_id = _to_int(ids.get("simkl"))
    if simkl_id is None:
        return None
    return {
        "simkl_id": simkl_id,
        "anilist_id": _to_int(ids.get("anilist")),
        "mal_id": _to_int(ids.get("mal")),
        "kitsu_id": _to_int(ids.get("kitsu")),
        "mapped_seasons": _normalize_mapped_seasons(data.get("mapped_tvdb_seasons")),
        "relations": _normalize_relations(data.get("relations")),
        "total_episodes": _to_int(data.get("total_episodes")),
    }


def _normalize_mapped_seasons(value: Any) -> List[int]:
    """Coerce ``mapped_tvdb_seasons`` into a list of ints, dropping garbage."""
    seasons: List[int] = []
    if isinstance(value, list):
        for item in value:
            season = _to_int(item)
            if season is not None:
                seasons.append(season)
    return seasons


def _normalize_relations(value: Any) -> List[Dict[str, Any]]:
    """Normalize the ``relations`` list into the shape the season walk reads.

    Every dict-shaped relation is kept (whatever its type): the season walk is
    responsible for filtering to ``sequel`` entries. Relations without a Simkl
    id keep ``None`` so the walk can skip them defensively.
    """
    relations: List[Dict[str, Any]] = []
    if not isinstance(value, list):
        return relations
    for item in value:
        if not isinstance(item, dict):
            continue
        ids = item.get("ids")
        ids = ids if isinstance(ids, dict) else {}
        relations.append(
            {
                "simkl_id": _to_int(ids.get("simkl")),
                "relation_type": _to_str(item.get("relation_type")),
                "year": _to_int(item.get("year")),
                "title": _first_str(item.get("en_title"), item.get("title")),
            }
        )
    return relations


def _first_str(*values: Any) -> Optional[str]:
    for value in values:
        text = _to_str(value)
        if text:
            return text
    return None


def _request(endpoint: str, params: Dict[str, Any]) -> Any:
    """Send a GET request to Simkl and return the parsed payload, or None."""
    try:
        response = requests.get(
            f"{SIMKL_BASE_URL}/{endpoint}",
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=10,
        )
    except Exception as error:
        kodilog(f"simkl: request failed for {endpoint}: {error}")
        return None
    if response.status_code != 200:
        kodilog(f"simkl: unexpected status {response.status_code} for {endpoint}")
        return None
    try:
        return response.json()
    except Exception as error:
        kodilog(f"simkl: invalid json for {endpoint}: {error}")
        return None


def _extract_ids(data: Any) -> Optional[Dict[str, Any]]:
    """Extract the ``ids`` block from a Simkl response."""
    entry: Any = None
    if isinstance(data, list) and data:
        entry = data[0]
    elif isinstance(data, dict):
        entry = data
    if not isinstance(entry, dict):
        return None
    ids = entry.get("ids")
    if not isinstance(ids, dict):
        return None
    return ids


def _to_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
