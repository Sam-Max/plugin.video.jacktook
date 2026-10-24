from unittest.mock import MagicMock, patch

import pytest

from lib.clients.debrid.torbox import TorboxException, TorboxHelper
from lib.utils.general.utils import filter_debrid_episode


@pytest.fixture
def helper():
    helper = TorboxHelper()
    helper.client = MagicMock()
    helper.client.create_download_link.return_value = {"data": "https://download"}
    files = [
        {"id": 1, "name": "Show.S01E01.mkv", "size": 400},
        {"id": 2, "name": "Show.S01E02.mkv", "size": 700},
        {"id": 3, "name": "Show.S01E03.mkv", "size": 1000},
        {"id": 4, "name": "Show.S02E02.mkv", "size": 1200},
        {"id": 5, "name": "Show.S01E02.txt", "size": 2000},
    ]
    with patch.object(helper, "add_torbox_torrent", return_value={"id": 10, "files": files}), patch(
        "lib.clients.debrid.torbox.EXTENSIONS", [".mkv"]
    ), patch("lib.clients.debrid.torbox.get_public_ip", return_value="192.0.2.1"):
        yield helper


def test_selects_requested_season_and_episode_instead_of_largest_file(helper):
    data = {"tv_data": {"season": 1, "episode": 2}}

    result = helper.get_link("hash", data)

    assert result is data
    assert result["url"] == "https://download"
    helper.client.create_download_link.assert_called_once_with(10, 2, "192.0.2.1")


@pytest.mark.parametrize("file_count", [1, 5])
def test_missing_episode_does_not_create_a_link_or_change_input(helper, file_count):
    helper.add_torbox_torrent.return_value["files"] = helper.add_torbox_torrent.return_value[
        "files"
    ][:file_count]
    data = {"tv_data": {"season": 1, "episode": 9}}

    with pytest.raises(TorboxException, match="No matching episode found in torrent"):
        helper.get_link("hash", data)

    assert data == {"tv_data": {"season": 1, "episode": 9}}
    helper.client.create_download_link.assert_not_called()


def test_movie_keeps_largest_video_selection(helper):
    result = helper.get_link("hash", {"title": "Movie"})

    assert result["url"] == "https://download"
    helper.client.create_download_link.assert_called_once_with(10, 4, "192.0.2.1")


@pytest.mark.parametrize("other_episode", ["S01E020", "S01E20", "S11E02"])
def test_episode_matching_does_not_accept_numeric_prefixes(helper, other_episode):
    helper.add_torbox_torrent.return_value["files"] = [
        {"id": 2, "name": "Show.S01E02.mkv", "size": 700},
        {"id": 20, "name": f"Show.{other_episode}.mkv", "size": 2000},
    ]

    result = helper.get_link("hash", {"tv_data": {"season": 1, "episode": 2}})

    assert result["url"] == "https://download"
    helper.client.create_download_link.assert_called_once_with(10, 2, "192.0.2.1")


def test_shared_matcher_keeps_existing_default_behavior():
    files = [
        {"name": "Show.S01E02.mkv"},
        {"name": "Show.S01E020.mkv"},
        {"name": "Show.cap.09.mkv"},
    ]

    assert filter_debrid_episode(files, episode_num=2, season_num=1) == files
    assert filter_debrid_episode(files, episode_num=2, season_num=1, exact_match=True) == files[:1]


def test_manual_pack_selection_keeps_explicit_file_id(helper):
    data = {
        "tv_data": {"season": 1, "episode": 2},
        "pack_info": {"torrent_id": 10, "file_id": 1},
    }

    result = helper.get_pack_link(data)

    assert result is data
    assert result["url"] == "https://download"
    helper.client.create_download_link.assert_called_once_with(10, 1, "192.0.2.1")
    helper.add_torbox_torrent.assert_not_called()


def test_cloud_selection_keeps_explicit_file_id(helper):
    data = {"torrent_id": 10, "file_id": 1, "tv_data": {"season": 1, "episode": 2}}

    result = helper.get_link("hash", data)

    assert result is data
    assert result["url"] == "https://download"
    helper.client.create_download_link.assert_called_once_with(10, 1, "192.0.2.1")
    helper.add_torbox_torrent.assert_not_called()


@pytest.mark.parametrize("route", ["normal", "cloud", "pack"])
def test_torbox_resolution_logs_timed_stages_without_private_data(helper, route):
    helper.client.create_download_link.return_value = {
        "data": "https://private.invalid/secret-token"
    }
    with patch("xbmc.log") as logger:
        if route == "normal":
            helper.get_link("hash", {"title": "PRIVATE_TITLE"})
        elif route == "cloud":
            helper.get_link("hash", {"torrent_id": 10, "file_id": 1})
        else:
            helper.get_pack_link({"pack_info": {"torrent_id": 10, "file_id": 1}})
    lines = [item.args[0] for item in logger.call_args_list if "[PLAYBACK-TIMING]" in item.args[0]]
    assert any("stage=torbox_public_ip" in line for line in lines)
    assert any("stage=torbox_download_link" in line for line in lines)
    assert any("stage=torbox_metadata" in line for line in lines) == (route == "normal")
    assert not any(
        secret in "\n".join(lines)
        for secret in ("private.invalid", "secret-token", "192.0.2.1", "PRIVATE_TITLE")
    )


def test_season_scheme_mismatch_still_finds_the_episode(helper):
    """TMDB seasons and release seasons differ; the episode number still identifies it."""
    helper.add_torbox_torrent.return_value["files"] = [
        {"id": 1, "name": "[Group] Show S01E01 1080p.mkv", "size": 400},
        {"id": 2, "name": "[Group] Show S01E02 1080p.mkv", "size": 700},
        {"id": 3, "name": "[Group] Show S01E03 1080p.mkv", "size": 1000},
    ]

    result = helper.get_link("hash", {"tv_data": {"season": 2, "episode": 2}})

    assert result["url"] == "https://download"
    helper.client.create_download_link.assert_called_once_with(10, 2, "192.0.2.1")


def test_season_less_retry_still_rejects_a_missing_episode(helper):
    helper.add_torbox_torrent.return_value["files"] = [
        {"id": 1, "name": "[Group] Show S01E01 1080p.mkv", "size": 400},
        {"id": 2, "name": "[Group] Show S01E02 1080p.mkv", "size": 700},
    ]

    with pytest.raises(TorboxException, match="No matching episode found in torrent"):
        helper.get_link("hash", {"tv_data": {"season": 2, "episode": 9}})

    helper.client.create_download_link.assert_not_called()


def test_shared_matcher_retries_without_the_season():
    files = [
        {"name": "Show.S01E01.mkv"},
        {"name": "Show.S01E02.mkv"},
        {"name": "Show.S01E03.mkv"},
    ]

    assert filter_debrid_episode(files, episode_num=2, season_num=2, exact_match=True) == files[1:2]


def test_shared_matcher_keeps_the_primary_result_instead_of_merging():
    files = [
        {"name": "Show.S02E02.mkv"},
        {"name": "Show.S01E02.mkv"},
    ]

    # Already answered: the retry must not widen to episode-only hits.
    assert filter_debrid_episode(files, episode_num=2, season_num=2, exact_match=True) == files[:1]


def test_shared_matcher_retry_does_not_match_a_numeric_prefix():
    files = [
        {"name": "Show.S01E020.mkv"},
        {"name": "Show.S01E02.mkv"},
    ]

    assert filter_debrid_episode(files, episode_num=2, season_num=9, exact_match=True) == files[1:]


def test_anime_episode_finds_the_cour_local_file(helper):
    """TMDB names the arc episode 49; the pack numbers it 9 of its own cour."""
    helper.add_torbox_torrent.return_value["files"] = [
        {"id": 8, "name": "[Group] Bleach Kashin-tan S01E08 1080p.mkv", "size": 700},
        {"id": 9, "name": "[Group] Bleach Kashin-tan S01E09 1080p.mkv", "size": 800},
    ]

    result = helper.get_link("hash", {"tv_data": {"season": 2, "episode": 49, "anime_episode": 9}})

    assert result["url"] == "https://download"
    helper.client.create_download_link.assert_called_once_with(10, 9, "192.0.2.1")


def test_arc_episode_wins_before_the_cour_local_one(helper):
    helper.add_torbox_torrent.return_value["files"] = [
        {"id": 49, "name": "[Group] Bleach TYBW S01E49 1080p.mkv", "size": 900},
        {"id": 9, "name": "[Group] Bleach Kashin-tan S01E09 1080p.mkv", "size": 800},
    ]

    result = helper.get_link("hash", {"tv_data": {"season": 2, "episode": 49, "anime_episode": 9}})

    assert result["url"] == "https://download"
    helper.client.create_download_link.assert_called_once_with(10, 49, "192.0.2.1")


def test_shared_matcher_uses_extra_numbers_only_after_the_primary_fails():
    files = [
        {"name": "Show.S01E08.mkv"},
        {"name": "Show.S01E09.mkv"},
    ]

    # 49 absent: the cour-local 9 answers.
    assert (
        filter_debrid_episode(
            files, episode_num=49, season_num=2, exact_match=True, extra_episode_nums=(9,)
        )
        == files[1:]
    )

    # 8 present: the primary number wins and 9 is never consulted.
    assert (
        filter_debrid_episode(
            files, episode_num=8, season_num=2, exact_match=True, extra_episode_nums=(9,)
        )
        == files[:1]
    )


def test_shared_matcher_ignores_unusable_extra_numbers():
    files = [{"name": "Show.S01E09.mkv"}]

    assert (
        filter_debrid_episode(
            files,
            episode_num=9,
            season_num=2,
            exact_match=True,
            extra_episode_nums=(None, "", "abc", 0, -3),
        )
        == files
    )
