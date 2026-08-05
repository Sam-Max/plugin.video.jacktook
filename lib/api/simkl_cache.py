import contextlib
from datetime import timedelta

from lib.db.cached import cache

SIMKL_CACHE_TTL = timedelta(minutes=5)
SIMKL_LIBRARY_CACHE_PREFIX = "simkl.library."
SIMKL_PLAYBACK_CACHE_KEY = "simkl.playback"
SIMKL_WATCHED_CACHE_PREFIX = "simkl.watched."
SIMKL_RATINGS_CACHE_PREFIX = "simkl.ratings."


def get_cached(key):
    try:
        return cache.get(key)
    except Exception:
        return None


def set_cached(key, value):
    with contextlib.suppress(Exception):
        cache.set(key, value, expires=SIMKL_CACHE_TTL)


def watched_cache_key(descriptors):
    return f"{SIMKL_WATCHED_CACHE_PREFIX}{tuple(descriptors)!r}"


def invalidate_library_cache():
    cache.delete_like(f"{SIMKL_LIBRARY_CACHE_PREFIX}%")


def invalidate_playback_cache():
    cache.delete(SIMKL_PLAYBACK_CACHE_KEY)


def invalidate_watched_cache():
    cache.delete_like(f"{SIMKL_WATCHED_CACHE_PREFIX}%")


def invalidate_ratings_cache():
    cache.delete_like(f"{SIMKL_RATINGS_CACHE_PREFIX}%")


def clear_simkl_cache():
    with contextlib.suppress(Exception):
        invalidate_library_cache()
    with contextlib.suppress(Exception):
        invalidate_playback_cache()
    with contextlib.suppress(Exception):
        invalidate_watched_cache()
    with contextlib.suppress(Exception):
        invalidate_ratings_cache()
