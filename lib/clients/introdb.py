"""IntroDB v3 client for intro, recap and ending (credits) segments."""

from datetime import timedelta

import requests

from lib.db.cached import MemoryCache
from lib.utils.kodi.utils import kodilog

INTRODB_BASE_URL = "https://api.theintrodb.org/v3"
INTRODB_SEGMENTS_PATH = "/media"
INTRODB_TIMEOUT = 5
INTRODB_CACHE_EXPIRY = timedelta(hours=24)

_DEFAULT_CONFIDENCE = 0.5
_DEFAULT_SUBMISSION_COUNT = 1
_SUBMISSION_COUNT_WEIGHT = 0.001

# IntroDB segment types consumed by the addon. The "preview" type is
# intentionally ignored: trailers are out of scope for the skip feature.
_SEGMENT_TYPE_MAP = (
    ("intro", "intro"),
    ("recap", "recap"),
    ("credits", "outro"),
)

_cache = MemoryCache(database="introdb")
_SENTINEL = "__introdb_none__"


def _coerce_positive_int(value):
    """Return value as a positive int, or None when it is not usable."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _coerce_float(value, default):
    """Return value as a float, or default when it is not usable."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _select_id(ids):
    """
    Pick exactly one IntroDB identifier using the v3 precedence rules.

    Args:
        ids: dict carrying the optional "tmdb_id", "tvdb_id" and "imdb_id" keys.

    Returns:
        tuple(str, object) with the query parameter name and value, or None
        when no identifier qualifies.
    """
    if not isinstance(ids, dict):
        return None

    # tmdb_id wins over tvdb_id; both must coerce to a positive integer.
    for key in ("tmdb_id", "tvdb_id"):
        number = _coerce_positive_int(ids.get(key))
        if number is not None:
            return key, number

    imdb_id = ids.get("imdb_id")
    if isinstance(imdb_id, str) and imdb_id.startswith("tt"):
        return "imdb_id", imdb_id

    return None


def _segment_score(candidate):
    """Score a candidate segment as confidence + 0.001 * submission_count."""
    confidence = _coerce_float(candidate.get("confidence"), _DEFAULT_CONFIDENCE)
    submission_count = _coerce_float(candidate.get("submission_count"), _DEFAULT_SUBMISSION_COUNT)
    return confidence + _SUBMISSION_COUNT_WEIGHT * submission_count


def _normalize_candidate(candidate):
    """
    Normalize a single IntroDB segment entry.

    Returns:
        dict with millisecond and second boundaries, or None when the entry is
        unusable (not an object, missing boundaries or an empty range).
    """
    if not isinstance(candidate, dict):
        return None

    start_ms = candidate.get("start_ms")
    end_ms = candidate.get("end_ms")
    if start_ms is None or end_ms is None:
        return None

    try:
        start_ms = int(start_ms)
        end_ms = int(end_ms)
    except (TypeError, ValueError):
        return None

    if end_ms <= start_ms:
        return None

    return {
        "start_ms": start_ms,
        "end_ms": end_ms,
        "start_sec": start_ms / 1000.0,
        "end_sec": end_ms / 1000.0,
    }


def _pick_best_segment(candidates):
    """Return the highest scoring usable candidate, or None."""
    best_segment = None
    best_score = None

    for candidate in candidates or []:
        segment = _normalize_candidate(candidate)
        if segment is None:
            continue

        score = _segment_score(candidate)
        if best_score is None or score > best_score:
            best_segment = segment
            best_score = score

    return best_segment


def _extract_segments(data):
    """Map the IntroDB segment types to the segment names used by the addon."""
    segments = {}

    for api_type, segment_type in _SEGMENT_TYPE_MAP:
        segment = _pick_best_segment(data.get(api_type))
        if segment is not None:
            segments[segment_type] = segment

    return segments


def get_segments(ids, season, episode):
    """
    Fetch intro, recap and ending segments from IntroDB (v3) for an episode.

    Exactly one identifier is sent: "tmdb_id" wins over "tvdb_id", which wins
    over "imdb_id". Results are cached in memory for 24 hours, and negative
    lookups (not found, error body or no usable segments) are cached as well.

    Args:
        ids: dict with optional "tmdb_id", "tvdb_id" and "imdb_id" entries.
        season: Season number (int)
        episode: Episode number (int)

    Returns:
        dict keyed by 'intro', 'recap' or 'outro', each value carrying
        'start_ms', 'end_ms', 'start_sec' and 'end_sec'. Types without usable
        segments are omitted, and None is returned when nothing is usable.
    """
    selected_id = _select_id(ids)
    if selected_id is None:
        kodilog("IntroDB: No usable media id, skipping request")
        return None

    season_number = _coerce_positive_int(season)
    episode_number = _coerce_positive_int(episode)
    if season_number is None or episode_number is None:
        kodilog("IntroDB: Missing or invalid season/episode, skipping request")
        return None

    id_key, id_value = selected_id
    cache_key = f"{id_key}:{id_value}.S{season_number}E{episode_number}"

    cached = _cache.get(cache_key)
    if cached is not None:
        if cached == _SENTINEL:
            kodilog(f"IntroDB: Cache hit (no data) for {cache_key}")
            return None
        kodilog(f"IntroDB: Cache hit for {cache_key}")
        return cached

    request_params = {
        id_key: id_value,
        "season": season_number,
        "episode": episode_number,
    }

    kodilog(
        f"IntroDB: Requesting {INTRODB_SEGMENTS_PATH} for {cache_key} with params {request_params}"
    )

    try:
        response = requests.get(
            f"{INTRODB_BASE_URL}{INTRODB_SEGMENTS_PATH}",
            params=request_params,
            timeout=INTRODB_TIMEOUT,
        )
    except requests.exceptions.Timeout:
        kodilog(f"IntroDB: Request timed out for {cache_key}")
        return None
    except requests.exceptions.RequestException as e:
        kodilog(f"IntroDB: Request failed for {cache_key}: {e}")
        return None

    status_code = response.status_code
    kodilog(f"IntroDB: Response status {status_code} for {cache_key} body={response.text}")

    if status_code == 404:
        kodilog(f"IntroDB: No segments found for {cache_key}")
        _cache.set(cache_key, _SENTINEL, expires=INTRODB_CACHE_EXPIRY)
        return None

    if status_code != 200:
        kodilog(f"IntroDB: Unexpected status {status_code} for {cache_key}")
        return None

    try:
        data = response.json()
    except ValueError as e:
        kodilog(f"IntroDB: Failed to parse response for {cache_key}: {e}")
        return None

    if not isinstance(data, dict):
        kodilog(f"IntroDB: Unexpected response payload for {cache_key} body={data}")
        return None

    if data.get("error"):
        kodilog(f"IntroDB: No media found for {cache_key} error={data.get('error')}")
        _cache.set(cache_key, _SENTINEL, expires=INTRODB_CACHE_EXPIRY)
        return None

    segments = _extract_segments(data)
    if not segments:
        kodilog(f"IntroDB: No usable segments for {cache_key} body={data}")
        _cache.set(cache_key, _SENTINEL, expires=INTRODB_CACHE_EXPIRY)
        return None

    kodilog(f"IntroDB: Got segments for {cache_key}: {sorted(segments)}")
    _cache.set(cache_key, segments, expires=INTRODB_CACHE_EXPIRY)
    return segments
