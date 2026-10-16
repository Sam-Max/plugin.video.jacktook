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
