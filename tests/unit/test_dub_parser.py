"""Offline tests for the dub release-name parser and badge builder."""

import pytest

from lib.utils.parsers.dub import apply_dub_badge, detect_dub


@pytest.mark.parametrize(
    "title,expected",
    [
        ("One Piece - 1091 [LATINO] 1080p", "LATINO"),
        ("Anime S01 [LatAm] WEB-DL", "LATINO"),
        ("Anime [Castellano] 1080p", "CASTELLANO"),
        ("One Piece - 1091 [DUBBED]", "DUB"),
        ("Release DUBLADO 1080p", "DUB"),
        ("Anime DOBLADAS completas", "DUB"),
        ("Temporada con DOBLAJE oficial", "DUB"),
        ("Show DUB proper", "DUB"),
        # Precedence: the first matching marker names the flavour.
        ("DOBLAJE latino 1080p", "LATINO"),
        # Language names alone are never a dub signal.
        ("Sub Español 1080p", ""),
        ("Anime SPANISH AUDIO-VOSTFR", ""),
        ("VOSTFR 1080p", ""),
        # Word boundaries: 'dub' must not leak into other words.
        ("Double trouble 1080p", ""),
        ("Subtitles included", ""),
        ("", ""),
        (None, ""),
    ],
)
def test_detect_dub(title, expected):
    assert detect_dub(title) == expected


def test_apply_dub_badge_appends_to_existing_badges():
    badges = "[B][COLOR CCFFFFFF]CODEC:[/COLOR] [COLOR CCAA2233]H264[/COLOR][/B]"

    result = apply_dub_badge(badges, "One Piece - 1091 [LATINO]")

    assert result.startswith(badges)
    assert "DUB:" in result
    assert "LATINO" in result


def test_apply_dub_badge_without_existing_badges():
    result = apply_dub_badge("", "One Piece - 1091 [DUBBED]")

    assert "DUB:" in result
    assert "DUB" in result


def test_apply_dub_badge_passes_plain_badges_through():
    badges = "some badges"

    assert apply_dub_badge(badges, "plain sub release") == badges
