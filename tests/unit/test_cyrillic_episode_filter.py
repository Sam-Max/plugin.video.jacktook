"""Episode filter for Russian/Ukrainian tracker titles (JacRed, Rutracker, Kinozal).

These trackers name packs by the episode range they hold instead of SxxEyy. The
English "1x01" pattern happened to match "[01x01-08 из 10]" for episode 1 only, so the
same packs were kept for episode 1 and dropped for episode 2.
"""

from typing import List
from unittest.mock import patch

import pytest

from lib.domain.torrent import TorrentStream
from lib.utils.general.processors import PreProcessBuilder, cyrillic_episode_coverage


def _kept_titles(
    titles: List[str], episode_num: int, season_num: int = 1, season_packs=False
) -> List[str]:
    builder = PreProcessBuilder([TorrentStream(title=title) for title in titles])
    with patch("lib.utils.general.processors.get_setting") as get_setting:
        get_setting.side_effect = lambda key, default=None: {
            "include_season_packs": season_packs
        }.get(key, default)
        builder.filter_sources("", episode_num, season_num)
    return [result.title for result in builder.results]


@pytest.mark.parametrize(
    "title",
    [
        "Король Талсы / Tulsa King [01x01-08 из 10] (2022) WEB-DLRip | LostFilm",
        "Король Талсы / Tulsa King [01-02x01-18 из 19] (2022-2024) WEB-DLRip | LostFilm",
        "Король Талсы (1 сезон: 1-9 серии из 9) / Tulsa King / 2022-2023 / WEB-DL (1080p)",
        "Король Талсы (1-2 сезоны: 1-19 серии из 19) / Tulsa King / WEB-DLRip",
        "Король Талсы / Tulsa King / Сезон: 1 / Серии: 1-9 из 9 [2022, WEB-DLRip]",
        "Король Талсы (Tulsa King) Сезон 1 Серии 01-09 (HD1080p WEBRip) Полный 1 сезон",
        "Король Талсы / Tulsa King (2022) WEBRip [H.264/720p] (сезон 1, серии 1-9 из 9)",
        "Король Талсы 1 сезон (1-9 из 9) / Tulsa King (2022) WEB-DLRip",
        "Король Талси / Tulsa King (Сезон 1-3) (2022-2025) WEBRip Ukr/Eng",
        "Король Талси / Tulsa King (Сезон 1, серії 1-8 з 10) WEBRip Ukr/Eng",
        "Король Талсы / Tulsa King / 1 сезон 2 серия [2022, 1080p] | [LostFilm]",
    ],
)
def test_releases_holding_the_episode_are_kept(title):
    assert _kept_titles([title], episode_num=2) == [title]


@pytest.mark.parametrize(
    "title",
    [
        "Король Талсы / Tulsa King / 1 сезон 1 серия [2022, 1080p] | [LostFilm]",
        "Король Талсы (1 сезон: 9 серия из 10) / Tulsa King / WEBRip",
        "Король Талсы / Tulsa King [01x01-08 из 10] (2022) WEB-DLRip",
        "Король Талсы / Tulsa King [02x01-08 из 10] (2024) WEB-DLRip",
        "Король Талсы (2 сезон: 1-9 серии из 9) / Tulsa King / WEB-DLRip",
        "Король Талсы / Tulsa King (2022) WEB-DL 1920x1080",
    ],
)
def test_releases_without_the_episode_are_dropped(title):
    assert _kept_titles([title], episode_num=9 if "01-08" in title else 2) == []


def test_season_marker_is_not_read_as_an_episode():
    # "Сезон 1 Серии 01-09" must not be read as episode 1 only.
    assert cyrillic_episode_coverage("Шоу Сезон 1 Серии 01-09", 1, 5) == "episode"


def test_whole_season_pack_follows_the_season_pack_setting():
    title = "Король Талси (Сезон 1) / Tulsa King WEB-DL 1080p Ukr"

    assert cyrillic_episode_coverage(title, 1, 2) == "season"
    assert _kept_titles([title], episode_num=2) == []
    assert _kept_titles([title], episode_num=2, season_packs=True) == [title]


def test_season_pack_and_episode_range_are_not_duplicated():
    title = "Tulsa King season 1 [01x01-08 из 10]"

    assert _kept_titles([title], episode_num=2, season_packs=True) == [title]


def test_multi_season_range_outside_the_episode_range_is_dropped():
    assert cyrillic_episode_coverage("[01-02x01-18 из 19]", 1, 30) is None


def test_multi_season_range_inside_the_episode_range_is_kept():
    assert cyrillic_episode_coverage("[01-02x01-18 из 19]", 2, 5) == "episode"


def test_cyrillic_multi_season_range_outside_the_episode_range_is_dropped():
    title = "Король Талсы (1-2 сезоны: 1-19 серии из 19) / Tulsa King / WEB-DLRip"

    assert cyrillic_episode_coverage(title, 1, 30) is None


def test_scene_episode_range_is_matched():
    assert cyrillic_episode_coverage("Show S01E01-E08", 1, 5) == "episode"
    assert cyrillic_episode_coverage("Show S01E01-E08", 1, 9) is None


def test_scene_episode_range_keeps_the_pack():
    title = "Show S01E01-E08 1080p"

    assert _kept_titles([title], episode_num=5) == [title]
    assert _kept_titles([title], episode_num=9) == []


def test_capitalized_season_pack_is_detected():
    title = "Tulsa King Season 1 1080p"

    assert _kept_titles([title], episode_num=2, season_packs=True) == [title]


def test_saison_season_pack_is_detected():
    title = "Tulsa King Saison 1 1080p"

    assert _kept_titles([title], episode_num=2, season_packs=True) == [title]


def test_parenthesized_season_marker_is_detected():
    title = "Tulsa King (S01) 1080p"

    assert _kept_titles([title], episode_num=2, season_packs=True) == [title]
