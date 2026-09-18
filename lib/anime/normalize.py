"""Pure normalization helpers for the anime metadata layer.

This module intentionally has no network, database or Kodi dependencies so it
can be imported and unit-tested standalone.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

ENGLISH = 0
ROMAJI = 1


@dataclass
class AnimeRecord:
    """Normalized anime metadata shared across providers."""

    anilist_id: Optional[int] = None
    mal_id: Optional[int] = None
    anidb_id: Optional[int] = None
    kitsu_id: Optional[int] = None
    tmdb_id: Optional[int] = None
    tvdb_id: Optional[int] = None
    imdb_id: Optional[str] = None
    simkl_id: Optional[int] = None
    title_en: Optional[str] = None
    title_romaji: Optional[str] = None
    title_native: Optional[str] = None
    title_default: Optional[str] = None
    episodes: Optional[int] = None
    format: Optional[str] = None
    status: Optional[str] = None
    year: Optional[int] = None
    description: Optional[str] = None
    cover: Optional[str] = None
    banner: Optional[str] = None
    synonyms: List[str] = field(default_factory=list)


def pick_display_title(record: AnimeRecord, language: int = ENGLISH) -> Optional[str]:
    """Return the preferred title for the requested language.

    The fallback chain is: requested language, the other language, native,
    title_default and finally any other non-empty title.
    """
    if language == ROMAJI:
        requested, other = record.title_romaji, record.title_en
    else:
        requested, other = record.title_en, record.title_romaji

    candidates = [
        requested,
        other,
        record.title_native,
        record.title_default,
        record.title_en,
        record.title_romaji,
    ]
    for candidate in candidates:
        text = _to_str(candidate)
        if text:
            return text
    return None


def record_from_payloads(
    anilist: Optional[Dict[str, Any]] = None,
    simkl: Optional[Dict[str, Any]] = None,
    anizip: Optional[Dict[str, Any]] = None,
    seed: Optional[Dict[str, Any]] = None,
) -> AnimeRecord:
    """Merge provider payloads into a single AnimeRecord.

    Field precedence is anilist > simkl > anizip > seed. Every argument is
    optional and malformed input degrades to ``None`` fields rather than
    raising.
    """
    anilist_data = _as_dict(anilist)
    simkl_data = _as_dict(simkl)
    anizip_data = _as_dict(anizip)
    seed_data = _as_dict(seed)
    simkl_ids = _simkl_ids(simkl_data)

    title_block = _as_dict(anilist_data.get("title"))
    cover_block = _as_dict(anilist_data.get("coverImage"))
    start_date = _as_dict(anilist_data.get("startDate"))

    record = AnimeRecord()
    record.anilist_id = _to_int(
        _first_value(
            anilist_data.get("id"),
            simkl_ids.get("anilist"),
            simkl_ids.get("anilist_id"),
            anizip_data.get("anilist_id"),
            seed_data.get("anilist_id"),
        )
    )
    record.mal_id = _to_int(
        _first_value(
            anilist_data.get("idMal"),
            simkl_ids.get("mal"),
            simkl_ids.get("mal_id"),
            anizip_data.get("mal_id"),
            seed_data.get("mal_id"),
        )
    )
    record.anidb_id = _to_int(
        _first_value(
            simkl_ids.get("anidb"),
            simkl_ids.get("anidb_id"),
            seed_data.get("anidb_id"),
        )
    )
    record.kitsu_id = _to_int(
        _first_value(
            simkl_ids.get("kitsu"),
            simkl_ids.get("kitsu_id"),
            seed_data.get("kitsu_id"),
        )
    )
    record.tmdb_id = _to_int(
        _first_value(
            simkl_ids.get("tmdb"),
            simkl_ids.get("tmdb_id"),
            anizip_data.get("tmdb_id"),
            seed_data.get("tmdb_id"),
        )
    )
    record.tvdb_id = _to_int(
        _first_value(
            simkl_ids.get("tvdb"),
            simkl_ids.get("tvdb_id"),
            anizip_data.get("tvdb_id"),
            anizip_data.get("thetvdb_id"),
            seed_data.get("tvdb_id"),
        )
    )
    record.imdb_id = _to_str(
        _first_value(
            simkl_ids.get("imdb"),
            simkl_ids.get("imdb_id"),
            anizip_data.get("imdb_id"),
            seed_data.get("imdb_id"),
        )
    )
    record.simkl_id = _to_int(
        _first_value(
            simkl_ids.get("simkl"),
            simkl_ids.get("simkl_id"),
            seed_data.get("simkl_id"),
        )
    )

    record.title_en = _to_str(
        _first_value(
            title_block.get("english"),
            simkl_data.get("en_title"),
            seed_data.get("title_en"),
        )
    )
    record.title_romaji = _to_str(
        _first_value(
            title_block.get("romaji"),
            simkl_data.get("romaji"),
            seed_data.get("title_romaji"),
        )
    )
    record.title_native = _to_str(
        _first_value(
            title_block.get("native"),
            seed_data.get("title_native"),
        )
    )
    record.title_default = _to_str(
        _first_value(
            record.title_en,
            record.title_romaji,
            record.title_native,
            simkl_data.get("title"),
            seed_data.get("title_default"),
        )
    )

    record.episodes = _to_int(
        _first_value(
            anilist_data.get("episodes"),
            simkl_data.get("episodes"),
            seed_data.get("episodes"),
        )
    )
    record.format = _to_str(_first_value(anilist_data.get("format"), seed_data.get("format")))
    record.status = _to_str(_first_value(anilist_data.get("status"), seed_data.get("status")))
    record.year = _to_int(
        _first_value(start_date.get("year"), simkl_data.get("year"), seed_data.get("year"))
    )
    record.description = _to_str(
        _first_value(
            anilist_data.get("description"),
            simkl_data.get("overview"),
            seed_data.get("description"),
        )
    )
    record.cover = _to_str(_first_value(cover_block.get("large"), seed_data.get("cover")))
    record.banner = _to_str(_first_value(anilist_data.get("bannerImage"), seed_data.get("banner")))

    synonyms = anilist_data.get("synonyms")
    if isinstance(synonyms, list):
        record.synonyms = [str(item) for item in synonyms if item]
    else:
        record.synonyms = []
    return record


def _simkl_ids(simkl_data: Dict[str, Any]) -> Dict[str, Any]:
    nested = simkl_data.get("ids")
    if isinstance(nested, dict):
        return nested
    return simkl_data


def _as_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _first_value(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
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
