from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Iterable, Optional

_PACK_TYPES = {
    "season",
    "multi_season",
    "complete_unknown",
    "unknown",
    "episode",
    "none",
    "mismatch",
}

_EPISODE_PATTERNS = (
    re.compile(r"(?<![A-Z0-9])S0*(\d{1,2})[\s._-]*E0*(\d{1,3})(?!\d)"),
    re.compile(r"(?<!\d)(\d{1,2})[\s._-]*X[\s._-]*0*(\d{1,3})(?!\d)"),
    re.compile(
        r"\b(?:SEASON|SAISON)\s*0*(\d{1,2})\s*"
        r"(?:EPISODE|EP)\s*0*(\d{1,3})\b"
    ),
)

_RANGE_PATTERNS = (
    re.compile(
        r"(?<![A-Z0-9])S0*(\d{1,2})\s*(?:-|TO|THROUGH|A)\s*"
        r"S0*(\d{1,2})(?!\d)"
    ),
    re.compile(
        r"\b(?:SEASONS?|SAISONS?)\s*0*(\d{1,2})\s*"
        r"(?:-|TO|THROUGH|A)\s*0*(\d{1,2})\b"
    ),
)

_COMPLETE_PATTERNS = (
    re.compile(r"\bCOMPLETE\s+(?:TV\s+)?SERIES\b"),
    re.compile(r"\bFULL\s+SERIES\b"),
    re.compile(r"\bALL\s+SEASONS\b"),
    re.compile(r"\bCOMPLETE\s+COLLECTION\b"),
    re.compile(r"\bINTEGRALE\b"),
    re.compile(r"\bSERIE\s+COMPLETE\b"),
    re.compile(r"\bSERIES\s+COMPLETE\b"),
)


def _normalize_title(title: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(title or ""))
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = normalized.upper().replace("_", " ").replace(".", " ")
    return re.sub(r"\s+", " ", normalized).strip()


def _positive_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _scope(
    is_pack: bool,
    pack_type: str,
    seasons: Iterable[int] = (),
    reason: str = "",
) -> Dict[str, Any]:
    normalized_type = pack_type if pack_type in _PACK_TYPES else "unknown"
    normalized_seasons = sorted(
        {season for season in (_positive_int(value) for value in seasons) if season is not None}
    )
    return {
        "is_pack": bool(is_pack),
        "pack_type": normalized_type,
        "pack_seasons": normalized_seasons,
        "pack_reason": reason,
    }


def detect_pack_scope(
    title: Any,
    current_season: Any = None,
    source_is_pack: bool = False,
) -> Dict[str, Any]:
    """Infer whether a TV release is an episode, season pack, or series pack.

    Explicit episode markers always win. Cross-season reuse is only possible
    later when the title explicitly lists a season range or multiple seasons.
    """
    normalized = _normalize_title(title)
    current = _positive_int(current_season)

    for pattern in _EPISODE_PATTERNS:
        if pattern.search(normalized):
            return _scope(False, "episode", reason="explicit episode marker")

    seasons = set()
    for pattern in _RANGE_PATTERNS:
        match = pattern.search(normalized)
        if not match:
            continue
        start = _positive_int(match.group(1))
        end = _positive_int(match.group(2))
        if start is None or end is None or start > end or end - start > 99:
            continue
        seasons.update(range(start, end + 1))

    seasons.update(
        int(value)
        for value in re.findall(r"(?<![A-Z0-9])S0*(\d{1,2})(?!\d|E)", normalized)
        if int(value) > 0
    )
    seasons.update(
        int(value)
        for value in re.findall(r"\b(?:SEASON|SAISON)\s*0*(\d{1,2})\b", normalized)
        if int(value) > 0
    )

    if seasons:
        if current is not None and current not in seasons:
            return _scope(False, "mismatch", seasons, "explicit seasons exclude current season")
        if len(seasons) == 1:
            return _scope(True, "season", seasons, "single explicit season without episode")
        return _scope(True, "multi_season", seasons, "explicit season range or list")

    if any(pattern.search(normalized) for pattern in _COMPLETE_PATTERNS):
        return _scope(True, "complete_unknown", reason="complete-series wording without range")

    if source_is_pack:
        return _scope(True, "unknown", reason="provider marked source as pack")

    return _scope(False, "none", reason="no pack evidence")


def playback_pack_scope(data: Dict[str, Any], current_season: Any = None) -> Dict[str, Any]:
    """Return normalized pack metadata from playback data, with title fallback."""
    stored_type = str(data.get("pack_type") or "")
    stored_seasons = data.get("pack_seasons")
    if stored_type in _PACK_TYPES and bool(data.get("is_pack")):
        if not isinstance(stored_seasons, (list, tuple, set)):
            stored_seasons = []
        return _scope(
            True,
            stored_type,
            stored_seasons,
            str(data.get("pack_reason") or "stored playback metadata"),
        )

    return detect_pack_scope(
        data.get("source_title") or "",
        current_season=current_season,
        source_is_pack=bool(data.get("is_pack")),
    )


def pack_scope_allows_transition(
    scope: Dict[str, Any],
    current_season: Any,
    next_season: Any,
) -> bool:
    """Return whether the same pack safely covers the requested transition."""
    current = _positive_int(current_season)
    target = _positive_int(next_season)
    if current is None or target is None or not scope.get("is_pack"):
        return False

    if current == target:
        return scope.get("pack_type") in {
            "season",
            "multi_season",
            "complete_unknown",
            "unknown",
        }

    if scope.get("pack_type") != "multi_season":
        return False

    seasons = {
        season
        for season in (_positive_int(value) for value in scope.get("pack_seasons", []))
        if season is not None
    }
    return current in seasons and target in seasons
