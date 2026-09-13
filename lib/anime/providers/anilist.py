"""Unauthenticated AniList GraphQL client for the anime metadata layer."""

import threading
import time
from datetime import timedelta
from typing import Any, Dict, List, Optional

import requests

from lib.db.cached import MemoryCache
from lib.utils.kodi.logging import kodilog

ANILIST_URL = "https://graphql.anilist.co"
USER_AGENT = "jacktook-anime/1.0"
CACHE_TTL = timedelta(hours=24)
MIN_REQUEST_GAP = 0.7

_CACHE = MemoryCache(database="jacktook.anime.anilist")
_REQUEST_LOCK = threading.Lock()
_last_request_time = 0.0


ANIME_FIELDS = """
    id
    idMal
    title {
        romaji
        english
        native
    }
    synonyms
    format
    status
    episodes
    duration
    description
    coverImage {
        large
    }
    bannerImage
    startDate {
        year
    }
"""

MEDIA_BY_ID_QUERY = "query ($id: Int) { Media(id: $id, type: ANIME) { " + ANIME_FIELDS + " } }"
MEDIA_BY_MAL_QUERY = (
    "query ($idMal: Int) { Media(idMal: $idMal, type: ANIME) { " + ANIME_FIELDS + " } }"
)
SEARCH_QUERY = (
    "query ($query: String, $page: Int, $perPage: Int) { "
    "Page(page: $page, perPage: $perPage) { "
    "media(search: $query, type: ANIME) { " + ANIME_FIELDS + " } } }"
)


def fetch_by_anilist_id(anilist_id: Optional[int]) -> Optional[Dict[str, Any]]:
    """Fetch a single anime by its AniList id."""
    if anilist_id is None:
        return None
    key = f"anilist:id:{anilist_id}"
    cached = _CACHE.get(key)
    if isinstance(cached, dict):
        return cached
    payload = _post(MEDIA_BY_ID_QUERY, {"id": anilist_id})
    media = _extract_media(payload)
    if media is not None:
        _CACHE.set(key, media, expires=CACHE_TTL)
    return media


def fetch_by_mal_id(mal_id: Optional[int]) -> Optional[Dict[str, Any]]:
    """Fetch a single anime by its MyAnimeList id."""
    if mal_id is None:
        return None
    key = f"anilist:mal:{mal_id}"
    cached = _CACHE.get(key)
    if isinstance(cached, dict):
        return cached
    payload = _post(MEDIA_BY_MAL_QUERY, {"idMal": mal_id})
    media = _extract_media(payload)
    if media is not None:
        _CACHE.set(key, media, expires=CACHE_TTL)
    return media


def search_anime(query: str, page: int = 1, per_page: int = 15) -> Optional[List[Dict[str, Any]]]:
    """Search for anime by title and return the matching media objects."""
    if not query:
        return None
    key = f"anilist:search:{query}:{page}:{per_page}"
    cached = _CACHE.get(key)
    if isinstance(cached, list):
        return cached
    variables = {"query": query, "page": page, "perPage": per_page}
    payload = _post(SEARCH_QUERY, variables)
    results = _extract_search(payload)
    if results is not None:
        _CACHE.set(key, results, expires=CACHE_TTL)
    return results


def _throttle() -> None:
    """Enforce a minimum gap between consecutive AniList requests."""
    global _last_request_time
    with _REQUEST_LOCK:
        elapsed = time.monotonic() - _last_request_time
        wait = MIN_REQUEST_GAP - elapsed
        if wait > 0:
            time.sleep(wait)
        _last_request_time = time.monotonic()


def _post(query: str, variables: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Send a GraphQL request and return the parsed payload, or None on error."""
    _throttle()
    try:
        response = requests.post(
            ANILIST_URL,
            json={"query": query, "variables": variables},
            headers={"Accept": "application/json", "User-Agent": USER_AGENT},
            timeout=10,
        )
    except Exception as error:
        kodilog(f"anilist: request failed: {error}")
        return None
    if response.status_code != 200:
        kodilog(f"anilist: unexpected status {response.status_code}")
        return None
    try:
        payload = response.json()
    except Exception as error:
        kodilog(f"anilist: invalid json: {error}")
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _extract_media(payload: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Extract the ``Media`` object from an AniList payload."""
    if not payload:
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    media = data.get("Media")
    if not isinstance(media, dict):
        return None
    return media


def _extract_search(payload: Optional[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
    """Extract the media list from an AniList search payload."""
    if not payload:
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    page = data.get("Page")
    if not isinstance(page, dict):
        return None
    media = page.get("media")
    if not isinstance(media, list):
        return None
    return [item for item in media if isinstance(item, dict)]
