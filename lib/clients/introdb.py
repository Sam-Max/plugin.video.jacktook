import requests
from datetime import timedelta
from lib.db.cached import MemoryCache
from lib.utils.kodi.utils import kodilog

INTRODB_BASE_URL = "http://api.introdb.app"
INTRODB_TIMEOUT = 5
INTRODB_CACHE_EXPIRY = timedelta(hours=24)

_cache = MemoryCache(database="introdb")
_SENTINEL = "__introdb_none__"


def get_segments(imdb_id, season, episode):
    """
    Fetch intro/recap/outro segment timestamps from IntroDB for a given episode.
    Results are cached in memory for 24 hours to avoid redundant API calls.

    Args:
        imdb_id: IMDb ID string (e.g., "tt0944947")
        season: Season number (int)
        episode: Episode number (int)

    Returns:
        dict with keys 'intro', 'recap', 'outro' (each a dict or None),
        or None if the request fails or no data is available.
    """
    if not imdb_id or not season or not episode:
        return None

    cache_key = f"{imdb_id}.S{season}E{episode}"

    # Check cache first
    cached = _cache.get(cache_key)
    if cached is not None:
        if cached == _SENTINEL:
            kodilog(f"IntroDB: Cache hit (no data) for {imdb_id} S{season}E{episode}")
            return None
        kodilog(f"IntroDB: Cache hit for {imdb_id} S{season}E{episode}")
        return cached

    try:
        response = requests.get(
            f"{INTRODB_BASE_URL}/segments",
            params={
                "imdb_id": imdb_id,
                "season": int(season),
                "episode": int(episode),
            },
            timeout=INTRODB_TIMEOUT,
        )

        if response.status_code == 404:
            kodilog(f"IntroDB: No segments found for {imdb_id} S{season}E{episode}")
            _cache.set(cache_key, _SENTINEL, expires=INTRODB_CACHE_EXPIRY)
            return None

        if response.status_code != 200:
            kodilog(
                f"IntroDB: Unexpected status {response.status_code} for {imdb_id} S{season}E{episode}"
            )
            return None

        data = response.json()
        kodilog(
            f"IntroDB: Got segments for {imdb_id} S{season}E{episode}: "
            f"intro={'yes' if data.get('intro') else 'no'}, "
            f"recap={'yes' if data.get('recap') else 'no'}, "
            f"outro={'yes' if data.get('outro') else 'no'}"
        )
        _cache.set(cache_key, data, expires=INTRODB_CACHE_EXPIRY)
        return data

    except requests.exceptions.Timeout:
        kodilog(f"IntroDB: Request timed out for {imdb_id} S{season}E{episode}")
        return None
    except requests.exceptions.RequestException as e:
        kodilog(f"IntroDB: Request failed for {imdb_id} S{season}E{episode}: {e}")
        return None
    except (ValueError, KeyError) as e:
        kodilog(
            f"IntroDB: Failed to parse response for {imdb_id} S{season}E{episode}: {e}"
        )
        return None
