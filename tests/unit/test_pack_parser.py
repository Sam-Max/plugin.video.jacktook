import pytest

from lib.utils.parsers.pack_parser import (
    detect_pack_scope,
    pack_scope_allows_transition,
)


@pytest.mark.parametrize(
    "title",
    [
        "Show.S05E03.1080p.WEB-DL",
        "Show 5x03 1080p",
        "Show Season 5 Episode 3",
    ],
)
def test_explicit_episode_is_never_inferred_as_pack(title):
    scope = detect_pack_scope(title, current_season=5, source_is_pack=True)

    assert scope["is_pack"] is False
    assert scope["pack_type"] == "episode"


def test_single_season_title_is_inferred_as_season_pack():
    scope = detect_pack_scope(
        "Le monde incroyable de Gumball s05 vff webrip aac -llam",
        current_season=5,
    )

    assert scope["is_pack"] is True
    assert scope["pack_type"] == "season"
    assert scope["pack_seasons"] == [5]


@pytest.mark.parametrize(
    "title,expected",
    [
        ("Show.S01-S06.Complete.1080p", [1, 2, 3, 4, 5, 6]),
        ("Show Seasons 1-6 Complete", [1, 2, 3, 4, 5, 6]),
        ("Show Saisons 1 a 6 Integrale", [1, 2, 3, 4, 5, 6]),
        ("Show.S01.S02.S03.MULTi", [1, 2, 3]),
    ],
)
def test_explicit_multi_season_titles_record_covered_seasons(title, expected):
    scope = detect_pack_scope(title, current_season=2)

    assert scope["is_pack"] is True
    assert scope["pack_type"] == "multi_season"
    assert scope["pack_seasons"] == expected


@pytest.mark.parametrize(
    "title",
    [
        "Show Complete Series 1080p",
        "Show Full Series",
        "Show Integrale MULTi",
        "Show Serie Complete",
    ],
)
def test_unbounded_complete_series_is_conservative(title):
    scope = detect_pack_scope(title, current_season=5)

    assert scope["is_pack"] is True
    assert scope["pack_type"] == "complete_unknown"
    assert scope["pack_seasons"] == []
    assert pack_scope_allows_transition(scope, 5, 5) is True
    assert pack_scope_allows_transition(scope, 5, 6) is False


def test_explicit_multi_season_pack_can_cross_only_inside_range():
    scope = detect_pack_scope("Show.S01-S06.Complete", current_season=5)

    assert pack_scope_allows_transition(scope, 5, 6) is True
    assert pack_scope_allows_transition(scope, 6, 7) is False


def test_explicit_seasons_excluding_current_are_rejected():
    scope = detect_pack_scope("Show.S01-S04.Complete", current_season=5, source_is_pack=True)

    assert scope["is_pack"] is False
    assert scope["pack_type"] == "mismatch"
