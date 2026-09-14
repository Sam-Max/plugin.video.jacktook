"""Display helpers that turn resolved anime identities into menu titles.

Every function here is defensive: any provider or parsing failure degrades to
``None`` so callers can fall back to their existing title.
"""

from typing import Any, Dict, List, Optional

import xbmc

from lib.anime.identity import resolve_identity
from lib.anime.normalize import ENGLISH, ROMAJI, AnimeRecord, pick_display_title
from lib.anime.providers import anilist
from lib.utils.kodi.logging import kodilog


def resolve_menu_record(ids: Optional[Dict[str, Any]]) -> Optional[AnimeRecord]:
    """Resolve the canonical record for the given ids, or None. Never raises."""
    try:
        return resolve_identity(ids)
    except Exception:
        return None


def resolve_menu_title(ids: Optional[Dict[str, Any]], language: Any = ENGLISH) -> Optional[str]:
    """Resolve the preferred menu title for the given ids and language.

    ``language`` may be a raw setting value (for example a string) and is
    coerced safely. Returns ``None`` on any failure or missing title.
    """
    record = resolve_menu_record(ids)
    if record is None:
        return None
    return pick_display_title(record, _coerce_language(language))


def pick_original_title(record: Optional[AnimeRecord], language: Any = ENGLISH) -> Optional[str]:
    """Return the romaji/english title that is not the displayed one."""
    if record is None:
        return None
    display = pick_display_title(record, _coerce_language(language))
    if _coerce_language(language) == ROMAJI:
        candidates = (record.title_en, record.title_romaji)
    else:
        candidates = (record.title_romaji, record.title_en)
    for candidate in candidates:
        text = _to_text(candidate)
        if text and text != display:
            return text
    return None


def resolve_menu_extras(seed: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Resolve anime cast, staff and studio extras for a menu seed, or None.

    The identity record is resolved through the existing path; the extras are
    fetched from AniList only when that record carries an AniList or MAL id.
    Never raises.
    """
    try:
        record = resolve_menu_record(seed)
        if record is None:
            return None
        return _fetch_cast_and_studio(record)
    except Exception:
        return None


def _fetch_cast_and_studio(record: AnimeRecord) -> Optional[Dict[str, Any]]:
    """Fetch normalized extras for a record, or None when nothing is usable."""
    anilist_id = record.anilist_id
    mal_id = record.mal_id
    if anilist_id is None and mal_id is None:
        return None
    extras = anilist.media_cast_and_studio(anilist_id=anilist_id, mal_id=mal_id)
    if not isinstance(extras, dict):
        return None
    if not any(extras.get(field) for field in ("cast", "staff", "studios")):
        return None
    return extras


def apply_anime_extras(list_item: Any, extras: Optional[Dict[str, Any]]) -> None:
    """Apply anime cast, staff and studios to a Kodi list item.

    A no-op when there is nothing to apply, and never raises: a detail view must
    not break because AniList returned a partial or unusable payload.
    """
    try:
        if list_item is None or not isinstance(extras, dict):
            return
        actors = _build_actors(extras)
        studios = _clean_text_list(extras.get("studios"))
        if not actors and not studios:
            return
        info_tag = list_item.getVideoInfoTag()
        if actors:
            info_tag.setCast(actors)
        if studios:
            info_tag.setStudio(studios)
    except Exception as error:
        kodilog(f"anime extras render failed: {error}")


def _build_actors(extras: Dict[str, Any]) -> List[Any]:
    """Build actors from the cast entries (with images) and the staff entries.

    ``order`` follows the provider's own relevance ordering, matching the
    convention ``build_actor`` already uses for TMDB cast.
    """
    actors = []
    for field in ("cast", "staff"):
        for entry in _clean_entries(extras.get(field)):
            actors.append(_build_actor(entry, len(actors)))
    return actors


def _build_actor(entry: Dict[str, Any], order: int = 0) -> Any:
    """Build one ``xbmc.Actor`` following the existing cast convention."""
    return xbmc.Actor(
        name=_to_text(entry.get("name")) or "",
        role=_to_text(entry.get("role")) or "",
        thumbnail=_to_text(entry.get("image")) or "",
        order=order,
    )


def _clean_entries(value: Any) -> List[Dict[str, Any]]:
    """Return the named entries of a cast/staff list, if any."""
    if not isinstance(value, list):
        return []
    entries = []
    for item in value:
        if isinstance(item, dict) and _to_text(item.get("name")):
            entries.append(item)
    return entries


def _clean_text_list(value: Any) -> List[str]:
    """Return the non-empty strings of a list, if any."""
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        text = _to_text(item)
        if text:
            result.append(text)
    return result


def _coerce_language(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return ENGLISH


def _to_text(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None
