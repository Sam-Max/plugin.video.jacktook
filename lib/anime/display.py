"""Display helpers that turn resolved anime identities into menu titles.

Every function here is defensive: any provider or parsing failure degrades to
``None`` so callers can fall back to their existing title.
"""

from typing import Any, Dict, Optional

from lib.anime.identity import resolve_identity
from lib.anime.normalize import ENGLISH, ROMAJI, AnimeRecord, pick_display_title


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
