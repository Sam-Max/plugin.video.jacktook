"""Pure episode-numbering helpers for the anime metadata layer.

AniZip exposes **TVDB** season/episode numbers plus the original air date, while
callers usually hold absolute episode numbers (or TMDB-style numbering). The
helpers here translate between both without any network, database or Kodi
dependency, so they can be imported and unit-tested standalone.

Nothing in the addon consumes this module yet: a later phase wires it into anime
playback.
"""

from dataclasses import dataclass, replace
from datetime import date
from typing import Any, List, Optional, Tuple

_MATCH_AIR_DATE = "air_date"
_MATCH_SEASON_EPISODE = "season_episode"
_MATCH_POSITION = "position"


@dataclass
class EpisodeCoordinates:
    """Normalized playback coordinates for a single AniZip episode entry."""

    absolute: Optional[int] = None
    season: Optional[int] = None
    episode: Optional[int] = None
    tvdb_id: Optional[int] = None
    title: Optional[str] = None
    air_date: Optional[str] = None
    matched_by: Optional[str] = None


def build_index(episodes: Any) -> List[EpisodeCoordinates]:
    """Build a normalized, absolute-number-ordered index from AniZip episodes.

    ``episodes`` is the raw ``episodes`` mapping of an AniZip payload: keys are
    episode-number strings and values are per-episode dicts. The result is
    ordered by absolute episode number, falling back to the TVDB episode number
    and then to the mapping key. Unusable entries (non-dict values, or values
    without any usable number) are skipped, and garbage input yields an empty
    list. This function never raises.
    """
    if not isinstance(episodes, dict):
        return []
    ordered: List[Tuple[int, EpisodeCoordinates]] = []
    for key, raw in episodes.items():
        if not isinstance(raw, dict):
            continue
        absolute = _to_int(raw.get("absoluteEpisodeNumber"))
        episode = _to_int(raw.get("episodeNumber"))
        position = _first_int(absolute, episode, _to_int(key))
        if position is None:
            continue
        ordered.append(
            (
                position,
                EpisodeCoordinates(
                    absolute=absolute,
                    season=_to_int(raw.get("seasonNumber")),
                    episode=episode,
                    tvdb_id=_to_int(raw.get("tvdbId")),
                    title=_to_str(raw.get("title")),
                    air_date=_normalize_date(raw.get("airDate")),
                ),
            )
        )
    ordered.sort(key=lambda item: item[0])
    return [coordinates for _, coordinates in ordered]


def match_coordinates(
    index: Any, season: Any, episode: Any, air_date: Any = None
) -> Optional[EpisodeCoordinates]:
    """Match playback coordinates against an index built by :func:`build_index`.

    Strategies are tried in order and the winner records itself in
    ``matched_by``:

    1. ``"air_date"``: exact normalized ``YYYY-MM-DD`` equality. This is the
       only safe signal, because the index carries TVDB numbering.
    2. ``"season_episode"``: TVDB ``(season, episode)`` equality.
    3. ``"position"``: 1-based position of ``episode`` inside the index, applied
       only when the index holds a single distinct season **and** the requested
       season, when it is provided, is present in the index. Positions only line up
       for the season the index actually describes, so a requested season absent
       from the index yields ``None`` instead of a fabricated coordinate.

    ``season``, ``episode`` and ``air_date`` are coerced defensively, so raw
    string values are accepted. The index is never mutated. Returns ``None`` when
    nothing matches, for empty or garbage input and on any parsing failure; this
    function never raises.
    """
    entries = _as_entries(index)
    if not entries:
        return None

    target_date = _normalize_date(air_date)
    if target_date is not None:
        for entry in entries:
            if entry.air_date == target_date:
                return _matched(entry, _MATCH_AIR_DATE)

    target_season = _to_int(season)
    target_episode = _to_int(episode)
    if target_season is not None and target_episode is not None:
        for entry in entries:
            if entry.season == target_season and entry.episode == target_episode:
                return _matched(entry, _MATCH_SEASON_EPISODE)

    if target_episode is not None and _allows_position_fallback(entries, target_season):
        position = target_episode - 1
        if 0 <= position < len(entries):
            return _matched(entries[position], _MATCH_POSITION)
    return None


def resolve_episode(
    ids: Any, season: Any, episode: Any, air_date: Any = None
) -> Optional[EpisodeCoordinates]:
    """Resolve episode coordinates for the given ids through AniZip.

    Reads ``anilist_id``/``mal_id`` from ``ids``, fetches the AniZip mappings and
    matches ``(season, episode, air_date)`` against its episode index. The
    provider import is lazy so this module stays importable without network or
    database access. Every failure (missing ids, provider ``None``, no episodes,
    malformed payload, any exception) degrades to ``None``; this function never
    raises.
    """
    try:
        source = ids if isinstance(ids, dict) else None
        if not source:
            return None
        anilist_id = _to_int(source.get("anilist_id"))
        mal_id = _to_int(source.get("mal_id"))
        if anilist_id is None and mal_id is None:
            return None

        from lib.anime.providers import anizip

        payload = anizip.mappings(anilist_id=anilist_id, mal_id=mal_id)
        if not isinstance(payload, dict):
            return None
        index = build_index(payload.get("episodes"))
        if not index:
            return None
        return match_coordinates(index, season, episode, air_date)
    except Exception:
        return None


def _as_entries(index: Any) -> List[EpisodeCoordinates]:
    """Return the usable :class:`EpisodeCoordinates` entries of an index."""
    if not isinstance(index, (list, tuple)):
        return []
    return [entry for entry in index if isinstance(entry, EpisodeCoordinates)]


def _matched(entry: EpisodeCoordinates, reason: str) -> EpisodeCoordinates:
    """Return a copy of ``entry`` tagged with the winning strategy."""
    return replace(entry, matched_by=reason)


def _allows_position_fallback(
    entries: List[EpisodeCoordinates], target_season: Optional[int]
) -> bool:
    """Return True when ``entries`` may answer a request by episode position.

    The 1-based position mapping is only meaningful for the single season the index
    describes, and the requested season must not contradict it: when a season is
    requested it has to be one the index actually holds. Answering anyway would
    fabricate plausible coordinates for a season the index does not contain, where
    the honest answer is no match.
    """
    seasons = {entry.season for entry in entries if entry.season is not None}
    if len(seasons) != 1:
        return False
    return target_season is None or target_season in seasons


def _first_int(*values: Optional[int]) -> Optional[int]:
    for value in values:
        if value is not None:
            return value
    return None


def _normalize_date(value: Any) -> Optional[str]:
    """Normalize a date value to ``YYYY-MM-DD``, or None when unusable."""
    text = _to_str(value)
    if not text:
        return None
    candidate = text.split("T", 1)[0].strip()
    parts = candidate.split("-")
    if len(parts) != 3:
        return None
    try:
        year, month, day = (int(part) for part in parts)
        return date(year, month, day).isoformat()
    except ValueError:
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
