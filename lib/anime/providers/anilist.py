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

# The detail payload is fetched only from the anime detail view, never from the
# listing or playback paths. Its ``perPage`` values must stay in sync with the
# limits below; the normalizer also truncates so a drifted query cannot bloat a
# cached result.
CAST_LIMIT = 8
STAFF_LIMIT = 6

DETAIL_FIELDS = """
    studios(isMain: true) {
        edges {
            isMain
            node {
                id
                name
            }
        }
    }
    characters(sort: [ROLE, RELEVANCE, ID], perPage: 8) {
        edges {
            role
            node {
                id
                name {
                    full
                }
                image {
                    medium
                }
            }
        }
    }
    staff(sort: [RELEVANCE, ID], perPage: 6) {
        edges {
            role
            node {
                id
                name {
                    full
                }
            }
        }
    }
"""

MEDIA_BY_ID_DETAIL_QUERY = (
    "query ($id: Int) { Media(id: $id, type: ANIME) { " + DETAIL_FIELDS + " } }"
)
MEDIA_BY_MAL_DETAIL_QUERY = (
    "query ($idMal: Int) { Media(idMal: $idMal, type: ANIME) { " + DETAIL_FIELDS + " } }"
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


def media_cast_and_studio(
    anilist_id: Optional[int] = None, mal_id: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """Fetch cast, staff and main studios for a single anime.

    This is deliberately separate from ``ANIME_FIELDS``: it runs once per opened
    title from the detail view and is cached under its own namespace, so the
    listing cache and the small identity record stay untouched. Returns ``None``
    when no id is given or the payload cannot be used.
    """
    if anilist_id is not None:
        key = f"anilist:cast:id:{anilist_id}"
        query = MEDIA_BY_ID_DETAIL_QUERY
        variables: Dict[str, Any] = {"id": anilist_id}
    elif mal_id is not None:
        key = f"anilist:cast:mal:{mal_id}"
        query = MEDIA_BY_MAL_DETAIL_QUERY
        variables = {"idMal": mal_id}
    else:
        return None
    cached = _CACHE.get(key)
    if isinstance(cached, dict):
        return cached
    try:
        payload = _post(query, variables)
        extras = _normalize_cast_and_studio(_extract_media(payload))
    except Exception as error:
        kodilog(f"anilist: cast fetch failed: {error}")
        return None
    if extras is not None:
        _CACHE.set(key, extras, expires=CACHE_TTL)
    return extras


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


def _normalize_cast_and_studio(media: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Normalize a detail payload into cast, staff and main studio names."""
    if not isinstance(media, dict):
        return None
    return {
        "cast": _normalize_cast(media),
        "staff": _normalize_staff(media),
        "studios": _normalize_studios(media),
    }


def _normalize_cast(media: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return at most ``CAST_LIMIT`` cast entries in AniList order."""
    cast: List[Dict[str, Any]] = []
    for edge in _edges(media, "characters"):
        node = _as_dict(edge.get("node"))
        name = _node_name(node)
        if not name:
            continue
        cast.append(
            {
                "name": name,
                "role": _to_text(edge.get("role")) or "",
                "image": _node_image(node),
            }
        )
        if len(cast) >= CAST_LIMIT:
            break
    return cast


def _normalize_staff(media: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return at most ``STAFF_LIMIT`` staff entries in AniList order."""
    staff: List[Dict[str, Any]] = []
    for edge in _edges(media, "staff"):
        node = _as_dict(edge.get("node"))
        name = _node_name(node)
        if not name:
            continue
        staff.append({"name": name, "role": _to_text(edge.get("role")) or ""})
        if len(staff) >= STAFF_LIMIT:
            break
    return staff


def _normalize_studios(media: Dict[str, Any]) -> List[str]:
    """Return the non-empty main studio names."""
    studios: List[str] = []
    for edge in _edges(media, "studios"):
        node = _as_dict(edge.get("node"))
        name = _to_text(node.get("name"))
        if name:
            studios.append(name)
    return studios


def _edges(media: Dict[str, Any], field: str) -> List[Dict[str, Any]]:
    """Return the ``edges`` list of a connection field, ignoring bad shapes."""
    block = media.get(field)
    if not isinstance(block, dict):
        return []
    edges = block.get("edges")
    if not isinstance(edges, list):
        return []
    return [edge for edge in edges if isinstance(edge, dict)]


def _as_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _node_name(node: Dict[str, Any]) -> Optional[str]:
    """Return ``node.name.full`` as text, or None."""
    name = node.get("name")
    if isinstance(name, dict):
        return _to_text(name.get("full"))
    return None


def _node_image(node: Dict[str, Any]) -> str:
    """Return ``node.image.medium`` as text, or an empty string."""
    image = node.get("image")
    if isinstance(image, dict):
        return _to_text(image.get("medium")) or ""
    return ""


def _to_text(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None
