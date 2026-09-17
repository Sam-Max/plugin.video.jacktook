"""Absolute-episode matching in the local episode filter.

The filter keeps a release when its title looks like the episode being played.
Anime releases are frequently numbered absolutely ("Show - 05"), while the filter
only built ``S{ss}E{ee}``-style patterns, so those releases were dropped. These
tests pin the absolute patterns and, just as importantly, the unchanged behaviour
when no absolute episode is resolved. The last two tests pin the anime marker that
gates the absolute episode, because a marker that coerces to True by accident would
change every non-anime path.
"""

from typing import List, Optional
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import xbmc

from lib.domain.torrent import TorrentStream
from lib.utils.general.processors import PreProcessBuilder
from lib.utils.general.utils import truthy_param
from lib.utils.kodi.utils import build_url


def _kept_titles(
    titles: List[str],
    episode_name: str = "",
    episode_num: int = 1,
    season_num: int = 1,
    absolute_episode: Optional[int] = None,
) -> List[str]:
    """Run the real episode filter and return the titles it kept, in order."""
    builder = PreProcessBuilder([TorrentStream(title=title) for title in titles])
    with patch("lib.utils.general.processors.get_setting") as get_setting:
        # Season packs are a separate filter; keep this test on episode matching.
        get_setting.side_effect = lambda key, default=None: {"include_season_packs": False}.get(
            key, default
        )
        builder.filter_sources(episode_name, episode_num, season_num, absolute_episode)
    return [result.title for result in builder.results]


def test_absolute_dash_release_is_kept_only_with_absolute_episode():
    title = "[Salieri] Attack On Titan S1 - 01 (1080p) (HDR) [Dual Audio].mkv"

    assert _kept_titles([title], absolute_episode=1) == [title]
    # Same title without an absolute episode: the pre-existing filter drops it.
    assert _kept_titles([title]) == []


def test_absolute_number_kept_for_padded_and_plain_forms():
    dash_release = "Show - 05 (1080p).mkv"
    dotted_release = "Show.05.1080p-GROUP.mkv"

    assert _kept_titles([dash_release], absolute_episode=5) == [dash_release]
    assert _kept_titles([dash_release]) == []

    assert _kept_titles([dotted_release], absolute_episode=5) == [dotted_release]
    assert _kept_titles([dotted_release]) == []


def test_bracketed_absolute_number_is_kept():
    title = "Show [07] (1080p).mkv"

    assert _kept_titles([title], absolute_episode=7) == [title]
    assert _kept_titles([title]) == []


def test_letter_e_absolute_number_is_kept():
    title = "Show E12 1080p WEB-DL-GROUP.mkv"

    assert _kept_titles([title], absolute_episode=12) == [title]
    assert _kept_titles([title]) == []


def test_existing_patterns_are_unchanged():
    titles = [
        "Show.S01E05.1080p-GROUP.mkv",
        "Show.1x05.720p-GROUP.mkv",
        "Show.Cap.05.480p-GROUP.mkv",
    ]

    # No absolute episode: exactly the historical behaviour.
    assert _kept_titles(titles, season_num=1, episode_num=5) == titles
    # An absolute episode must only add patterns, never remove a match.
    assert _kept_titles(titles, season_num=1, episode_num=5, absolute_episode=5) == titles


def test_episode_name_matching_is_unchanged_with_absolute_episode():
    titles = ["Show.Kick-off.1080p-GROUP.mkv", "Show.Other.1080p-GROUP.mkv"]

    assert _kept_titles(titles, episode_name="Kick-off", absolute_episode=5) == [titles[0]]


def test_resolution_and_codec_noise_is_not_matched():
    title = "Noise.2024.1080p.x265.HEVC.WEB-DL-GROUP.mkv"

    # Every candidate number below only exists inside the noise above.
    for noisy_absolute in (5, 8, 10, 26, 65, 108):
        assert _kept_titles([title], absolute_episode=noisy_absolute) == []


def test_audio_channel_notation_is_not_matched_as_absolute_episode():
    # Audio-channel pairs ("5.1", "7.1", "2.0") must not match on either side: the
    # episode side must not swallow a trailing ".1", and the channel side must not
    # match as a bare number just because the decimal point acts as a separator.
    for title, episode_side, channel_side in (
        ("Show Special [EAC3 2.0].mkv", 2, None),
        ("DDP 5.1", 5, 1),
        ("AAC 5.1", 5, 1),
        ("FLAC 7.1", 7, 1),
        ("Show - 5.1 Audio Track", 5, 1),
    ):
        assert _kept_titles([title], absolute_episode=episode_side) == []
        if channel_side is not None:
            assert _kept_titles([title], absolute_episode=channel_side) == []


def test_bare_absolute_numbers_after_separators_still_match():
    # The audio-channel guard must not cost the plain bare-number matches.
    assert _kept_titles(["Show - 05"], absolute_episode=5) == ["Show - 05"]
    assert _kept_titles(["Show S1 - 01"], absolute_episode=1) == ["Show S1 - 01"]
    assert _kept_titles(["Show - 5"], absolute_episode=5) == ["Show - 5"]


def test_episode_filter_logs_absolute_episode_and_kept_count():
    titles = ["Show - 05 (1080p).mkv", "Show.S01E01.1080p-GROUP.mkv"]

    builder = PreProcessBuilder([TorrentStream(title=title) for title in titles])
    with patch("lib.utils.general.processors.get_setting") as get_setting, patch(
        "lib.utils.general.processors.kodilog"
    ) as kodilog:
        get_setting.side_effect = lambda key, default=None: {"include_season_packs": False}.get(
            key, default
        )
        builder.filter_sources("", 5, 1, 5)

    # The filter behaves exactly as before; only its evidence is new.
    assert [result.title for result in builder.results] == [titles[0]]

    anime_calls = [
        call for call in kodilog.call_args_list if call.args and "[ANIME]" in str(call.args[0])
    ]
    assert len(anime_calls) == 1
    message = str(anime_calls[0].args[0])
    assert "absolute_episode=5" in message
    assert "candidates=2" in message
    assert "kept=1" in message

    # Production Kodi runs with debug logging off, so a message left at the kodilog default
    # (LOGDEBUG) never reaches kodi.log. The filter must pin its own INFO level.
    levels = [call.args[1] if len(call.args) > 1 else None for call in anime_calls]
    assert levels == [xbmc.LOGINFO]


def test_unusable_absolute_values_add_no_patterns():
    absolute_release = "Show - 05 (1080p).mkv"
    existing_release = "Show.S01E05.1080p-GROUP.mkv"

    for unusable in (None, 0, -3, "5", 5.0, True):
        assert _kept_titles([absolute_release], absolute_episode=unusable) == []
        assert _kept_titles(
            [absolute_release, existing_release],
            season_num=1,
            episode_num=5,
            absolute_episode=unusable,
        ) == [existing_release]


def test_anime_marker_accepts_only_explicitly_enabled_values():
    assert truthy_param("1") is True
    assert truthy_param("true") is True
    assert truthy_param(True) is True

    for disabled in (None, "", "0", "false", False, 0, "2", "yes"):
        assert truthy_param(disabled) is False


def test_anime_marker_literal_survives_a_plugin_url():
    enabled = parse_qs(urlparse(build_url("search", anime="1")).query)
    disabled = parse_qs(urlparse(build_url("search", anime="0")).query)

    assert truthy_param(enabled["anime"][0]) is True
    assert truthy_param(disabled["anime"][0]) is False
