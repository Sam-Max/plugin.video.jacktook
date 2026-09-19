"""Detect dubbed releases from their names and build the source-select badge.

Only explicit dub markers trigger the badge. Generic language names
(``espanol``, ``spanish``, ``japanese``...) are deliberately excluded: the
classic release convention ``Sub Espanol`` means subtitled, so a bare language
name carries no dub signal.
"""

import re

from lib.utils.parsers.title_parser import get_color_tag

_DUB_COLOR = "FF7CFC00"

# Checked in order: the first matching marker names the dub flavour.
_DUB_MARKERS = (
    ("LATINO", re.compile(r"\blatino\b|\blatam\b", re.IGNORECASE)),
    ("CASTELLANO", re.compile(r"\bcastellano\b", re.IGNORECASE)),
    # dub / dubbed / dubs / dublado / doblada / doblado / doblaje...
    ("DUB", re.compile(r"\bdub(bed|lado|lada)?s?\b|\bdobl(aje|ada|ado)s?\b", re.IGNORECASE)),
)

_DUB_BADGE_SEPARATOR = "  [COLOR 80FFFFFF] • [/COLOR]  "


def detect_dub(title):
    """Return the dub flavour a release name declares, or an empty string.

    Args:
        title: The release name as shown to the user.

    Returns:
        "LATINO", "CASTELLANO" or "DUB" when the name carries an explicit dub
        marker, and "" otherwise. Language names alone never match.
    """
    title = title or ""
    for label, pattern in _DUB_MARKERS:
        if pattern.search(title):
            return label
    return ""


def apply_dub_badge(badges, title):
    """Append the dub badge to an existing badges line when the name declares it.

    Args:
        badges: The rendered badges line built by ``parse_title_info``.
        title: The release name as shown to the user.

    Returns:
        The badges line with the ``DUB: <flavour>`` tag appended (or just the
        tag when there were no badges), unchanged when the name is not dubbed.
    """
    marker = detect_dub(title)
    if not marker:
        return badges
    tag = get_color_tag("DUB:", marker, _DUB_COLOR)
    if not badges:
        return tag
    return f"{badges}{_DUB_BADGE_SEPARATOR}{tag}"
