import threading
from unittest.mock import MagicMock, patch

import pytest

from lib.api.debrid.base import ProviderException
from lib.clients.debrid.realdebrid import RealDebridHelper
from lib.domain.torrent import TorrentStream


def test_get_link_multi_file_movie_uses_largest_selected_file():
    helper = RealDebridHelper.__new__(RealDebridHelper)
    helper.client = MagicMock()
    helper.add_magnet = MagicMock(return_value="torrent-id")

    helper.client.get_torrent_info.return_value = {
        "links": ["link-small", "link-large", "link-medium"],
        "files": [
            {"selected": 1, "bytes": 100},
            {"selected": 1, "bytes": 300},
            {"selected": 1, "bytes": 200},
        ],
    }
    helper.client.create_download_link.side_effect = lambda link: {
        "download": f"https://download/{link}"
    }

    result = helper.get_link("info-hash", {})

    assert result is not None
    assert result["url"] == "https://download/link-large"
    assert "is_pack" not in result


def test_get_link_multi_file_movie_falls_back_to_pack_when_no_selected_files():
    helper = RealDebridHelper.__new__(RealDebridHelper)
    helper.client = MagicMock()
    helper.add_magnet = MagicMock(return_value="torrent-id")

    helper.client.get_torrent_info.return_value = {
        "links": ["link-one", "link-two"],
        "files": [{"selected": 0, "bytes": 100}, {"selected": 0, "bytes": 200}],
    }

    result = helper.get_link("info-hash", {})

    assert result is not None
    assert result["is_pack"] is True
    assert "url" not in result


def test_get_link_single_file_movie_returns_download_url():
    helper = RealDebridHelper.__new__(RealDebridHelper)
    helper.client = MagicMock()
    helper.add_magnet = MagicMock(return_value="torrent-id")

    helper.client.get_torrent_info.return_value = {
        "links": ["link-movie"],
        "files": [{"path": "/Movie.2025.1080p.mkv", "selected": 1, "bytes": 1000}],
    }
    helper.client.create_download_link.return_value = {"download": "https://download/movie"}

    result = helper.get_link("info-hash", {})

    assert result is not None
    assert result["url"] == "https://download/movie"
    assert "is_pack" not in result


def test_get_link_single_file_archive_raises_packed_release_error():
    helper = RealDebridHelper.__new__(RealDebridHelper)
    helper.client = MagicMock()
    helper.add_magnet = MagicMock(return_value="torrent-id")

    helper.client.get_torrent_info.return_value = {
        "links": ["link-rar"],
        "files": [{"path": "/Movie.2025.1080p.rar", "selected": 1, "bytes": 1000}],
    }

    with pytest.raises(ProviderException, match="Real-Debrid cannot directly play packed releases"):
        helper.get_link("info-hash", {})


def test_check_cached_downloading_torrent_is_uncached():
    helper = RealDebridHelper.__new__(RealDebridHelper)
    helper.client = MagicMock()
    helper.client.get_user_torrent_list.return_value = [
        {"hash": "hash-in-progress", "status": "downloading"}
    ]

    cached_results = []
    uncached_results = []
    results = [TorrentStream(infoHash="hash-in-progress")]

    with patch("lib.clients.debrid.realdebrid.get_setting", return_value=False):
        helper.check_cached(
            results,
            cached_results,
            uncached_results,
            1,
            MagicMock(),
            threading.Lock(),
        )

    assert [res.infoHash for res in cached_results] == []
    assert [res.infoHash for res in uncached_results] == ["hash-in-progress"]


def test_check_cached_downloaded_torrent_is_cached():
    helper = RealDebridHelper.__new__(RealDebridHelper)
    helper.client = MagicMock()
    helper.client.get_user_torrent_list.return_value = [
        {"hash": "hash-finished", "status": "downloaded"}
    ]

    cached_results = []
    uncached_results = []
    results = [TorrentStream(infoHash="hash-finished")]

    with patch("lib.clients.debrid.realdebrid.get_setting", return_value=False):
        helper.check_cached(
            results,
            cached_results,
            uncached_results,
            1,
            MagicMock(),
            threading.Lock(),
        )

    assert [res.infoHash for res in cached_results] == ["hash-finished"]
    assert uncached_results == []


def test_check_max_active_count_deletes_oldest_when_at_limit():
    helper = RealDebridHelper.__new__(RealDebridHelper)
    helper.client = MagicMock()
    helper.client.get_torrent_active_count.return_value = {"nb": 5, "limit": 5}
    helper.client.get_user_torrent_list.return_value = [
        {"id": "newer", "added": "2023-01-02T00:00:00.000Z"},
        {"id": "oldest", "added": "2023-01-01T00:00:00.000Z"},
    ]

    helper.check_max_active_count()

    helper.client.get_user_torrent_list.assert_called_once_with(filter="active")
    helper.client.delete_torrent.assert_called_once_with("oldest")


def test_check_max_active_count_below_limit_does_not_delete():
    helper = RealDebridHelper.__new__(RealDebridHelper)
    helper.client = MagicMock()
    helper.client.get_torrent_active_count.return_value = {"nb": 4, "limit": 5}

    helper.check_max_active_count()

    helper.client.delete_torrent.assert_not_called()


def test_check_max_active_count_empty_active_list_does_not_raise():
    helper = RealDebridHelper.__new__(RealDebridHelper)
    helper.client = MagicMock()
    helper.client.get_torrent_active_count.return_value = {"nb": 5, "limit": 5}
    helper.client.get_user_torrent_list.return_value = []

    helper.check_max_active_count()

    helper.client.delete_torrent.assert_not_called()


def test_check_max_active_count_malformed_response_does_not_raise():
    """The documented activeCount payload is an object; anything else must degrade."""
    helper = RealDebridHelper.__new__(RealDebridHelper)
    helper.client = MagicMock()
    helper.client.get_torrent_active_count.return_value = ["unexpected"]

    helper.check_max_active_count()

    helper.client.delete_torrent.assert_not_called()


def test_get_info_with_fractional_seconds_renders():
    helper = RealDebridHelper.__new__(RealDebridHelper)
    helper.client = MagicMock()
    helper.client.get_user.return_value = {
        "email": "user@example.com",
        "username": "testuser",
        "type": "premium",
        "expiration": "2023-01-01T00:00:00.000Z",
        "points": 100,
    }

    with patch("lib.clients.debrid.realdebrid.dialog_text") as mock_dialog_text:
        helper.get_info()

    mock_dialog_text.assert_called_once()
    body = mock_dialog_text.call_args[0][1]
    assert "2023-01-01 00:00:00" in body
    assert "Days Remaining" in body


def test_get_info_without_fractional_seconds_renders():
    helper = RealDebridHelper.__new__(RealDebridHelper)
    helper.client = MagicMock()
    helper.client.get_user.return_value = {
        "email": "user@example.com",
        "username": "testuser",
        "type": "premium",
        "expiration": "2023-01-01T00:00:00Z",
        "points": 100,
    }

    with patch("lib.clients.debrid.realdebrid.dialog_text") as mock_dialog_text:
        helper.get_info()

    mock_dialog_text.assert_called_once()
    body = mock_dialog_text.call_args[0][1]
    assert "2023-01-01 00:00:00" in body
    assert "Unknown" not in body


def test_get_pack_link_rejects_non_numeric_file_position():
    helper = RealDebridHelper.__new__(RealDebridHelper)
    helper.client = MagicMock()
    helper.client.get_torrent_info.return_value = {"links": ["link-a", "link-b"]}

    data = {"pack_info": {"file_position": "", "torrent_id": "torrent-1"}}

    with pytest.raises(ProviderException, match="Could not map the selected pack file"):
        helper.get_pack_link(data)


def test_get_pack_link_rejects_out_of_range_file_position():
    helper = RealDebridHelper.__new__(RealDebridHelper)
    helper.client = MagicMock()
    helper.client.get_torrent_info.return_value = {"links": ["link-a"]}

    data = {"pack_info": {"file_position": 7, "torrent_id": "torrent-1"}}

    with pytest.raises(ProviderException, match="no longer available"):
        helper.get_pack_link(data)


def test_get_pack_link_returns_url_for_valid_file_position():
    helper = RealDebridHelper.__new__(RealDebridHelper)
    helper.client = MagicMock()
    helper.client.get_torrent_info.return_value = {"links": ["link-a", "link-b"]}
    helper.client.create_download_link.return_value = {"download": "https://download/b"}

    data = {"pack_info": {"file_position": 1, "torrent_id": "torrent-1"}}
    result = helper.get_pack_link(data)

    assert result is not None
    assert result["url"] == "https://download/b"
    helper.client.create_download_link.assert_called_once_with("link-b")


def test_get_link_unselected_episode_raises_provider_exception():
    """A matched episode that Real-Debrid has not selected must not raise ValueError."""
    helper = RealDebridHelper.__new__(RealDebridHelper)
    helper.client = MagicMock()
    helper.add_magnet = MagicMock(return_value="torrent-id")
    helper.client.get_torrent_info.return_value = {
        "links": ["link-1", "link-2"],
        "files": [
            {"path": "/Show/S01E03.mkv", "selected": 0, "bytes": 100},
            {"path": "/Show/S01E04.mkv", "selected": 0, "bytes": 200},
        ],
    }

    with pytest.raises(ProviderException, match="File is not cached"):
        helper.get_link("info-hash", {"tv_data": {"season": 1, "episode": 3}})


def test_get_pack_info_tolerates_path_without_slash():
    helper = RealDebridHelper.__new__(RealDebridHelper)
    helper.client = MagicMock()
    helper.add_magnet = MagicMock(return_value="torrent-id")
    helper.client.get_torrent_info.return_value = {
        "id": "torrent-id",
        "files": [
            {"id": 1, "path": "/Show/S01E01.mkv", "selected": 1},
            {"id": 2, "path": "FlatFile.mkv", "selected": 1},
        ],
    }

    with patch("lib.clients.debrid.realdebrid.get_cached", return_value=None), patch(
        "lib.clients.debrid.realdebrid.set_cached"
    ):
        info = helper.get_pack_info("info-hash")

    assert info is not None
    assert info["files"] == [(1, "Show/S01E01.mkv"), (2, "FlatFile.mkv")]


def test_get_pack_info_skips_single_file_torrents():
    helper = RealDebridHelper.__new__(RealDebridHelper)
    helper.client = MagicMock()
    helper.add_magnet = MagicMock(return_value="torrent-id")
    helper.client.get_torrent_info.return_value = {
        "id": "torrent-id",
        "files": [{"id": 1, "path": "/Only.mkv", "selected": 1}],
    }

    with patch("lib.clients.debrid.realdebrid.get_cached", return_value=None):
        with pytest.raises(ProviderException, match="No files on the current source"):
            helper.get_pack_info("info-hash")
