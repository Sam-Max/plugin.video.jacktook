"""IMDb ratings for list items, fetched in batches from IMDb's GraphQL API."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from typing import Dict, Iterable, List, Optional, Tuple

import requests

from lib.api.imdb.imdb_scraper import GQL_HEADERS, GQL_URL
from lib.db.cached import cache
from lib.utils.kodi.utils import kodilog

IMDB_BATCH_SIZE = 100
IMDB_RATING_TTL = timedelta(hours=24)
IMDB_ID_TTL = timedelta(days=30)
# List items carry these so add_directory_items_batch can rate a whole page at once.
IMDB_ID_PROPERTY = "jacktook.imdb.id"
IMDB_TMDB_REF_PROPERTY = "jacktook.imdb.tmdb_ref"
# Cached for titles IMDb has no rating for, so they are not asked for again every page.
NO_RATING = (0.0, 0)

Rating = Tuple[float, int]


def _rating_from_title(title) -> Optional[Rating]:
    summary = title.get("ratingsSummary") if isinstance(title, dict) else None
    if not isinstance(summary, dict):
        return None
    try:
        rating = float(summary.get("aggregateRating") or 0)
        votes = int(summary.get("voteCount") or 0)
    except (TypeError, ValueError):
        return None
    return (rating, votes)


def _fetch_ratings(imdb_ids: List[str]) -> Dict[str, Rating]:
    query = "{ titles(ids: %s) { id ratingsSummary { aggregateRating voteCount } } }" % (
        json.dumps(imdb_ids)
    )
    try:
        response = requests.post(GQL_URL, json={"query": query}, headers=GQL_HEADERS, timeout=10)
        response.raise_for_status()
        titles = (response.json().get("data") or {}).get("titles") or []
    except (requests.RequestException, ValueError, AttributeError) as error:
        kodilog(f"IMDb ratings request failed: {error}")
        return {}

    ratings = {}
    for title in titles:
        rating = _rating_from_title(title)
        if rating is not None and title.get("id") in imdb_ids:
            ratings[title["id"]] = rating
    return ratings


def get_imdb_ratings(imdb_ids: Iterable[str]) -> Dict[str, Rating]:
    """Return {imdb_id: (rating, votes)} for the ids IMDb has a rating for."""
    ratings: Dict[str, Rating] = {}
    missing = []
    for imdb_id in dict.fromkeys(i for i in imdb_ids if i and str(i).startswith("tt")):
        cached = cache.get(f"imdb_rating|{imdb_id}")
        if cached is not None:
            ratings[imdb_id] = tuple(cached)
        else:
            missing.append(imdb_id)

    for start in range(0, len(missing), IMDB_BATCH_SIZE):
        batch = missing[start : start + IMDB_BATCH_SIZE]
        fetched = _fetch_ratings(batch)
        if not fetched:
            continue
        for imdb_id in batch:
            rating = fetched.get(imdb_id, NO_RATING)
            cache.set(f"imdb_rating|{imdb_id}", rating, IMDB_RATING_TTL)
            ratings[imdb_id] = rating

    return {k: v for k, v in ratings.items() if v[0] > 0}


def _lookup_imdb_id(media_type: str, tmdb_id: str) -> str:
    from lib.clients.tmdb.utils.utils import tmdb_get

    path = "movie_external_ids" if media_type == "movie" else "tv_external_ids"
    try:
        data = tmdb_get(path, tmdb_id)
        return str(getattr(data, "imdb_id", "") or "")
    except Exception as error:
        kodilog(f"IMDb id lookup failed for {media_type} {tmdb_id}: {error}")
        return ""


def resolve_imdb_ids(items: Iterable[Tuple[str, str]]) -> Dict[Tuple[str, str], str]:
    """Map (media_type, tmdb_id) pairs, media_type "movie" or "tv", to IMDb ids."""
    resolved: Dict[Tuple[str, str], str] = {}
    missing = []
    for key in dict.fromkeys(items):
        cached = cache.get(f"imdb_id|{key[0]}|{key[1]}")
        if cached is not None:
            resolved[key] = cached
        else:
            missing.append(key)

    if missing:
        with ThreadPoolExecutor(max_workers=min(8, len(missing))) as executor:
            imdb_ids = list(executor.map(lambda key: _lookup_imdb_id(*key), missing))
        for key, imdb_id in zip(missing, imdb_ids):
            if imdb_id:
                cache.set(f"imdb_id|{key[0]}|{key[1]}", imdb_id, IMDB_ID_TTL)
            resolved[key] = imdb_id

    return {key: imdb_id for key, imdb_id in resolved.items() if imdb_id}


def _property(item, key) -> str:
    try:
        return item.getProperty(key) or ""
    except (AttributeError, TypeError):
        return ""


def _tmdb_ref(item) -> Optional[Tuple[str, str]]:
    media_type, _, tmdb_id = _property(item, IMDB_TMDB_REF_PROPERTY).partition(":")
    return (media_type, tmdb_id) if media_type in ("movie", "tv") and tmdb_id else None


def apply_imdb_ratings(items) -> None:
    """Set the IMDb rating as the default rating and as Label2 on directory items."""
    item_ids = []
    for _, item, _ in items:
        imdb_id = _property(item, IMDB_ID_PROPERTY)
        ref = None if imdb_id else _tmdb_ref(item)
        if imdb_id or ref:
            item_ids.append((item, imdb_id, ref))
    if not item_ids:
        return

    resolved = resolve_imdb_ids(ref for _, imdb_id, ref in item_ids if ref)
    item_ids = [
        (item, imdb_id or resolved.get(ref, ""), bool(ref)) for item, imdb_id, ref in item_ids
    ]
    ratings = get_imdb_ratings(imdb_id for _, imdb_id, _ in item_ids)

    for item, imdb_id, was_resolved in item_ids:
        rating = ratings.get(imdb_id)
        if not rating:
            continue
        try:
            info_tag = item.getVideoInfoTag()
            if was_resolved:
                info_tag.setIMDBNumber(imdb_id)
            info_tag.setRating(rating[0], rating[1], "imdb", True)
            item.setLabel2(f"{rating[0]:.1f}")
        except (AttributeError, TypeError) as error:
            kodilog(f"IMDb rating rendering failed ({type(error).__name__})")
