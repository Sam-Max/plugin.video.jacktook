"""Simkl public client used to resolve external anime ids."""

from datetime import timedelta
from typing import Any, Dict, Optional

import requests

from lib.db.cached import MemoryCache
from lib.utils.kodi.logging import kodilog

SIMKL_CLIENT_ID = "59dfdc579d244e1edf6f89874d521d37a69a95a1abd349910cb056a1872ba2c8"
SIMKL_BASE_URL = "https://api.simkl.com"
USER_AGENT = "jacktook-anime/1.0"
CACHE_TTL = timedelta(hours=24)

_CACHE = MemoryCache(database="jacktook.anime.simkl")


def resolve_ids(provider: str, value: Any) -> Optional[Dict[str, Any]]:
    """Resolve a normalized id block for a provider/value pair."""
    if not provider or value is None:
        return None
    key = f"simkl:search:{provider}:{value}"
    cached = _CACHE.get(key)
    if isinstance(cached, dict):
        return cached
    params = {provider: value, "client_id": SIMKL_CLIENT_ID}
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
    """Fetch the raw ``ids`` block for a Simkl anime entry."""
    if simkl_id is None:
        return None
    key = f"simkl:anime:{simkl_id}"
    cached = _CACHE.get(key)
    if isinstance(cached, dict):
        return cached
    params = {"extended": "full", "client_id": SIMKL_CLIENT_ID}
    data = _request(f"anime/{simkl_id}", params)
    ids = _extract_ids(data)
    if ids is None:
        return None
    _CACHE.set(key, ids, expires=CACHE_TTL)
    return ids


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
