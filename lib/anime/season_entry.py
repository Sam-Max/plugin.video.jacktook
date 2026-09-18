"""Per-season anime identity resolution across Simkl cour entries.

Simkl carries one entry per cour of a multi-cour anime: the base entry only
covers the seasons it aired, and later cours live in ``sequel`` relations that
publish their own ids and ``mapped_tvdb_seasons``.
:func:`resolve_season_entry` walks those relations so seasons beyond the base
entry (Mushoku Tensei season 3, for example) can still resolve to the entry
that actually aired them.
"""

from datetime import timedelta
from typing import Any, Dict, Optional

import xbmc

from lib.anime.providers.simkl import fetch_entry
from lib.db.cached import MemoryCache
from lib.utils.kodi.logging import kodilog

CACHE_TTL = timedelta(hours=24)

# Sequel chains are short in practice (one entry per cour), but the cap keeps a
# malformed or self-referential relation list from fanning out into unbounded
# fetches.
_MAX_RELATION_FETCHES = 12

_CACHE = MemoryCache(database="jacktook.anime.season_entry")


def resolve_season_entry(base_simkl_id: Any, season: Any) -> Optional[Dict[str, Any]]:
    """Return the ids of the Simkl entry covering ``season``, or ``None``.

    ``base_simkl_id`` is the entry the identity record already resolved. When
    it covers the requested season its own ids are returned; otherwise the
    base entry's ``sequel`` relations are walked in order and the first entry
    whose ``mapped_seasons`` contains the season wins. The returned dict holds
    ``{"simkl_id", "anilist_id", "mal_id", "kitsu_id"}``.

    Results are cached for 24h keyed ``"{base_simkl_id}:{season}"``; negative
    results are not cached so a failed walk can retry. Every failure (unusable
    input, provider failures, exhausted chain, any exception) degrades to
    ``None``; this function never raises.
    """
    try:
        base_id = _to_positive_int(base_simkl_id)
        season_number = _to_positive_int(season)
        if base_id is None or season_number is None:
            return None
        key = f"{base_id}:{season_number}"
        cached = _CACHE.get(key)
        if isinstance(cached, dict):
            return cached
        entry = _resolve_uncached(base_id, season_number)
        if entry is not None:
            _CACHE.set(key, entry, expires=CACHE_TTL)
        return entry
    except Exception as error:
        kodilog(f"anime season entry resolution failed: {error}")
        return None


def _resolve_uncached(base_id: int, season_number: int) -> Optional[Dict[str, Any]]:
    """Walk the base entry and its sequels for the entry covering the season."""
    base = fetch_entry(base_id)
    if base is None:
        kodilog(f"[ANIME] season walk aborted: Simkl entry {base_id} unavailable")
        return None
    if season_number in (base.get("mapped_seasons") or []):
        kodilog(
            f"[ANIME] season {season_number} covered by Simkl entry {base_id}",
            xbmc.LOGINFO,
        )
        return _entry_ids(base)
    fetches = 0
    for relation in base.get("relations") or []:
        if not isinstance(relation, dict) or not _is_sequel(relation):
            continue
        related_id = relation.get("simkl_id")
        if related_id is None:
            continue
        if fetches >= _MAX_RELATION_FETCHES:
            kodilog(f"[ANIME] season walk capped after {fetches} sequel fetches")
            break
        fetches += 1
        entry = fetch_entry(related_id)
        if entry is None:
            continue
        if season_number in (entry.get("mapped_seasons") or []):
            kodilog(
                f"[ANIME] season {season_number} resolved to Simkl entry "
                f"{related_id} after {fetches} sequel fetches",
                xbmc.LOGINFO,
            )
            return _entry_ids(entry)
    kodilog(
        f"[ANIME] season {season_number} not covered by Simkl entry {base_id} "
        f"or its sequels ({fetches} fetched)"
    )
    return None


def _entry_ids(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Return the id block of a normalized entry for routing."""
    return {
        "simkl_id": entry.get("simkl_id"),
        "anilist_id": entry.get("anilist_id"),
        "mal_id": entry.get("mal_id"),
        "kitsu_id": entry.get("kitsu_id"),
    }


def _is_sequel(relation: Dict[str, Any]) -> bool:
    """Return True when the relation is a sequel, tolerating case drift."""
    relation_type = relation.get("relation_type")
    return isinstance(relation_type, str) and relation_type.strip().lower() == "sequel"


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
