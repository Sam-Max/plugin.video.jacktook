"""AniSkip v2 client: crowd-sourced skip times for anime episodes.

AniSkip indexes opening (``op``), ending (``ed``) and recap intervals per
MyAnimeList id and episode number. The v2 API requires the episode runtime in
seconds and only returns intervals whose length is close to it, so callers must
pass the real duration once the player knows it.

The provider maps AniSkip types onto the same segment names the IntroDB client
and the player already speak (``intro``/``recap``/``outro``), so the player can
merge both sources without conversion. ``mixed-op`` intervals are intentionally
not requested: an opening overlapped with episode content is not a clean skip
boundary.
"""

from datetime import timedelta

import requests
import xbmc

from lib.db.cached import MemoryCache
from lib.utils.kodi.utils import kodilog

LOG = xbmc.LOGINFO

ANISKIP_BASE_URL = "https://api.aniskip.com/v2"
ANISKIP_TIMEOUT = 5
ANISKIP_CACHE_EXPIRY = timedelta(hours=24)

# AniSkip skip types requested and their addon segment names. The "mixed-op"
# type is deliberately absent: it overlaps the opening with episode content.
_SKIP_TYPE_MAP = {
    "op": "intro",
    "ed": "outro",
    "recap": "recap",
}

_cache = MemoryCache(database="jacktook.anime.aniskip")
_SENTINEL = "__aniskip_none__"


def _coerce_positive_int(value):
    """Return value as a positive int, or None when it is not usable."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _coerce_positive_float(value):
    """Return value as a positive float, or None when it is not usable."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _normalize_interval(interval):
    """
    Normalize one AniSkip ``interval`` object into player segment boundaries.

    AniSkip carries closed float-second ranges (``startTime``/``endTime``).

    Returns:
        dict with millisecond and second boundaries, or None when the entry is
        unusable (not an object, non-numeric boundaries, or an empty or
        reversed range).
    """
    if not isinstance(interval, dict):
        return None

    start_sec = _coerce_positive_float(interval.get("startTime"))
    end_sec = _coerce_positive_float(interval.get("endTime"))
    if start_sec is None or end_sec is None or end_sec <= start_sec:
        return None

    start_ms = int(start_sec * 1000)
    end_ms = int(end_sec * 1000)
    return {
        "start_ms": start_ms,
        "end_ms": end_ms,
        "start_sec": start_sec,
        "end_sec": end_sec,
    }


def _extract_segments(results):
    """Map AniSkip skip types to the segment names used by the addon."""
    segments = {}

    for result in results or []:
        if not isinstance(result, dict):
            continue
        skip_type = result.get("skipType")
        segment_name = _SKIP_TYPE_MAP.get(skip_type) if isinstance(skip_type, str) else None
        if segment_name is None or segment_name in segments:
            continue
        segment = _normalize_interval(result.get("interval"))
        if segment is not None:
            segments[segment_name] = segment

    return segments


def get_skip_times(mal_id, episode_number, episode_length_sec):
    """
    Fetch intro, ending and recap skip times from AniSkip (v2) for an episode.

    ``episode_length_sec`` is required by the API: AniSkip filters submitted
    intervals by proximity to the real runtime, so the caller should pass the
    duration the player reports. Results are cached in memory for 24 hours
    keyed by MAL id, episode and length; negative lookups (not found, bad
    request, no usable intervals) are cached as well.

    Args:
        mal_id: MyAnimeList id of the anime entry that aired the episode.
        episode_number: Episode number as AniSkip knows it (absolute number).
        episode_length_sec: Episode runtime in seconds, from the player.

    Returns:
        dict keyed by 'intro', 'recap' or 'outro', each value carrying
        'start_ms', 'end_ms', 'start_sec' and 'end_sec'. Types without usable
        intervals are omitted, and None is returned when nothing is usable.
    """
    mal_number = _coerce_positive_int(mal_id)
    episode = _coerce_positive_int(episode_number)
    length = _coerce_positive_float(episode_length_sec)
    if mal_number is None or episode is None or length is None:
        kodilog("AniSkip: invalid id, episode or length, skipping request", level=LOG)
        return None

    cache_key = f"aniskip:{mal_number}:{episode}:{int(length)}"
    cached = _cache.get(cache_key)
    if cached is not None:
        if cached == _SENTINEL:
            kodilog(f"AniSkip: cache hit (no data) for {cache_key}", level=LOG)
            return None
        kodilog(f"AniSkip: cache hit for {cache_key}", level=LOG)
        return cached

    request_params = {
        "types": list(_SKIP_TYPE_MAP),
        "episodeLength": length,
    }

    kodilog(
        f"AniSkip: requesting skip times for MAL {mal_number} episode {episode} "
        f"(length {int(length)}s)",
        level=LOG,
    )

    try:
        response = requests.get(
            f"{ANISKIP_BASE_URL}/skip-times/{mal_number}/{episode}",
            params=request_params,
            timeout=ANISKIP_TIMEOUT,
        )
    except requests.exceptions.Timeout:
        kodilog(f"AniSkip: request timed out for {cache_key}", level=LOG)
        return None
    except requests.exceptions.RequestException as e:
        kodilog(f"AniSkip: request failed for {cache_key}: {e}", level=LOG)
        return None

    status_code = response.status_code
    kodilog(
        f"AniSkip: response status {status_code} for {cache_key} body={response.text}",
        level=LOG,
    )

    if status_code in (404, 400):
        kodilog(f"AniSkip: no skip times for {cache_key}", level=LOG)
        _cache.set(cache_key, _SENTINEL, expires=ANISKIP_CACHE_EXPIRY)
        return None

    if status_code != 200:
        kodilog(f"AniSkip: unexpected status {status_code} for {cache_key}", level=LOG)
        return None

    try:
        data = response.json()
    except ValueError as e:
        kodilog(f"AniSkip: failed to parse response for {cache_key}: {e}", level=LOG)
        return None

    if not isinstance(data, dict) or not data.get("found"):
        kodilog(f"AniSkip: no usable payload for {cache_key} body={data}", level=LOG)
        _cache.set(cache_key, _SENTINEL, expires=ANISKIP_CACHE_EXPIRY)
        return None

    segments = _extract_segments(data.get("results"))
    if not segments:
        kodilog(f"AniSkip: no usable intervals for {cache_key} body={data}", level=LOG)
        _cache.set(cache_key, _SENTINEL, expires=ANISKIP_CACHE_EXPIRY)
        return None

    kodilog(f"AniSkip: got segments for {cache_key}: {sorted(segments)}", level=LOG)
    _cache.set(cache_key, segments, expires=ANISKIP_CACHE_EXPIRY)
    return segments


def merge_skip_segments(base, override):
    """
    Merge IntroDB and AniSkip segments into the player's segment store.

    AniSkip data is crowd-sourced specifically for anime episodes, so it wins
    per segment type; IntroDB fills the types AniSkip does not carry. Both
    inputs may be None or partial.

    Args:
        base: IntroDB segment dict (or None).
        override: AniSkip segment dict (or None).

    Returns:
        The merged dict, or None when neither source produced segments.
    """
    merged = dict(base) if isinstance(base, dict) else {}
    if isinstance(override, dict):
        merged.update(override)
    return merged or None
