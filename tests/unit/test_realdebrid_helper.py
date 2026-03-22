import pytest
from unittest.mock import MagicMock

from lib.api.debrid.base import ProviderException
from lib.clients.debrid.realdebrid import RealDebridHelper


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
        "download": "https://download/{}".format(link)
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
