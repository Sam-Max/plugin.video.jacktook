"""AniZip mappings client for the anime metadata layer."""

from datetime import timedelta
from typing import Any, Dict, Optional

import requests

from lib.db.cached import MemoryCache
from lib.utils.kodi.logging import kodilog

ANIZIP_URL = "https://api.ani.zip/mappings"
USER_AGENT = "jacktook-anime/1.0"
CACHE_TTL = timedelta(hours=24)

_CACHE = MemoryCache(database="jacktook.anime.anizip")


def mappings(
    anilist_id: Optional[int] = None, mal_id: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """Fetch normalized AniZip mappings for an AniList or MAL id."""
    if anilist_id is None and mal_id is None:
        return None
    if anilist_id is not None:
        params: Dict[str, Any] = {"anilist_id": anilist_id}
        key = f"anizip:anilist:{anilist_id}"
    else:
        params = {"mal_id": mal_id}
        key = f"anizip:mal:{mal_id}"
    cached = _CACHE.get(key)
    if isinstance(cached, dict):
        return cached
    result = _normalize_mappings(_request(params))
    if result is None:
        return None
    _CACHE.set(key, result, expires=CACHE_TTL)
    return result


def _request(params: Dict[str, Any]) -> Any:
    """Send a GET request to AniZip and return the parsed payload, or None."""
    try:
        response = requests.get(
            ANIZIP_URL,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=10,
        )
    except Exception as error:
        kodilog(f"anizip: request failed: {error}")
        return None
    if response.status_code != 200:
        kodilog(f"anizip: unexpected status {response.status_code}")
        return None
    try:
        return response.json()
    except Exception as error:
        kodilog(f"anizip: invalid json: {error}")
        return None


def _normalize_mappings(data: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(data, dict):
        return None
    raw = data.get("mappings")
    if not isinstance(raw, dict):
        raw = {}
    episodes = data.get("episodes")
    return {
        "anilist_id": _to_int(raw.get("anilist_id")),
        "mal_id": _to_int(raw.get("mal_id")),
        "tvdb_id": _to_int(raw.get("tvdb_id")),
        "thetvdb_id": _to_int(raw.get("thetvdb_id")),
        "imdb_id": _to_str(raw.get("imdb_id")),
        "tmdb_id": _to_int(_first_value(raw.get("tmdb_id"), raw.get("themoviedb_id"))),
        "episodes": episodes if isinstance(episodes, dict) else {},
    }


def _first_value(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return None


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
