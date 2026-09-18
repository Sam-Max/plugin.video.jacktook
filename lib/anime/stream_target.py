"""Stream routing targets for one anime episode.

Given the ids a playback path already holds, :func:`resolve_anime_route` resolves
the anime identity and its absolute episode number, and
:func:`pick_kitsu_target` turns that into the video id and episode number to send
to a stream addon. ``None`` always means "keep whatever the caller does today",
so the addon's existing routes are never bypassed by accident.

Nothing in the addon consumes this module yet: a later phase wires it into anime
playback.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from lib.anime.episode_map import resolve_episode
from lib.anime.identity import resolve_identity

# Ids that make an identity lookup worth its provider round-trips.
_USABLE_ID_KEYS = ("tmdb_id", "tvdb_id", "imdb_id", "anilist_id", "mal_id")

# Playback is always episodic anime, and the identity cache keys on every non-empty
# seed field, so the seed shape stays stable and minimal.
_SEED_ID_KEYS = ("tmdb_id", "tvdb_id", "imdb_id")


@dataclass(frozen=True)
class AnimeRoute:
    """Identity and numbering resolved for one anime episode."""

    kitsu_id: Optional[int]
    absolute: Optional[int]
    matched_by: Optional[str]
    anilist_id: Optional[int]
    mal_id: Optional[int]


@dataclass(frozen=True)
class StreamTarget:
    """The video id and episode number to send to a stream addon."""

    video_id: str
    episode: int
    kind: str  # routing family; always "kitsu" for now
    absolute: int


def resolve_anime_route(
    ids: Optional[Dict[str, Any]], season: Any, episode: Any, air_date: Any = None
) -> Optional[AnimeRoute]:
    """Resolve the anime identity and absolute numbering for one episode.

    The identity lookup costs provider round-trips (cached by the providers), so
    obviously unusable input is rejected before any call: no ids, no known id, or
    an uncoercible ``season``/``episode``. A ``None`` result is also a normal
    outcome when identity, the Kitsu id or the episode map cannot be resolved,
    and ``absolute`` may legitimately stay ``None`` even for a matched episode:
    callers decide through :func:`pick_kitsu_target`. This function never raises.
    """
    try:
        source = ids if isinstance(ids, dict) else None
        if not source or not _has_usable_id(source):
            return None
        if _to_int(season) is None or _to_int(episode) is None:
            return None

        record = resolve_identity(_identity_seed(source))
        if record is None or record.kitsu_id is None:
            return None

        coordinates = resolve_episode(
            {"anilist_id": record.anilist_id, "mal_id": record.mal_id},
            season,
            episode,
            air_date,
        )
        return AnimeRoute(
            kitsu_id=record.kitsu_id,
            absolute=_to_int(getattr(coordinates, "absolute", None)),
            matched_by=_to_str(getattr(coordinates, "matched_by", None)),
            anilist_id=record.anilist_id,
            mal_id=record.mal_id,
        )
    except Exception:
        return None


def pick_kitsu_target(
    route: Optional[AnimeRoute], season: Any, episode: Any
) -> Optional[StreamTarget]:
    """Pick the native Kitsu target for a resolved route, or ``None``.

    Pure: no network, no settings. ``None`` means the caller keeps its current
    behaviour, and an unusable route (no Kitsu id, or no positive absolute
    episode number) degrades to it. ``season`` and ``episode`` are accepted but
    deliberately unused: the Kitsu video id is season-less and already carries the
    absolute episode number, while keeping them in the signature gives the future
    caller a single stable call shape for every routing kind.
    """
    if route is None:
        return None
    absolute = _to_positive_int(route.absolute)
    kitsu_id = _to_positive_int(route.kitsu_id)
    if absolute is None or kitsu_id is None:
        return None
    return StreamTarget(
        video_id=f"kitsu:{kitsu_id}",
        episode=absolute,
        kind="kitsu",
        absolute=absolute,
    )


def supports_kitsu_target(target: Optional[StreamTarget]) -> bool:
    """Return True when the target is a usable native Kitsu route."""
    return bool(target is not None and target.kind == "kitsu" and target.episode > 0)


def _has_usable_id(source: Dict[str, Any]) -> bool:
    """Return True when the ids carry at least one value worth resolving."""
    return any(source.get(key) not in (None, "") for key in _USABLE_ID_KEYS)


def _identity_seed(source: Dict[str, Any]) -> Dict[str, Any]:
    """Build the identity seed: exactly the known ids plus the TV hint.

    The seed shape is intentionally fixed (including ``None`` values) because
    ``resolve_identity`` caches on every non-empty seed field.
    """
    seed: Dict[str, Any] = {key: source.get(key) for key in _SEED_ID_KEYS}
    seed["media_type"] = "tv"
    return seed


def _to_positive_int(value: Any) -> Optional[int]:
    number = _to_int(value)
    if number is None or number <= 0:
        return None
    return number


def _to_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_str(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None
