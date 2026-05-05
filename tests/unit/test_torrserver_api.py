"""Tests for TorrServer API client response normalization.

Regression tests for issue #193: TorrServer may return a JSON list
instead of a dict for some endpoints, causing TypeError when
accessing ["hash"] on the list.
"""

from unittest.mock import MagicMock, patch

import pytest

from lib.api.jacktorr.jacktorr import TorrServer, TorrServerError


def _make_response(json_data, status_code=200):
    """Create a mock requests.Response with the given json data and status code."""
    response = MagicMock()
    response.json.return_value = json_data
    response.status_code = status_code
    response.text = str(json_data)
    return response


@pytest.fixture
def torrserver():
    """Create a TorrServer instance with a mock session."""
    session = MagicMock()
    return TorrServer(
        host="localhost",
        port=8090,
        username="admin",
        password="pass",
        ssl_enabled=False,
        session=session,
    )


class TestNormalizeJsonResponse:
    """Tests for TorrServer._normalize_json_response."""

    def test_dict_passthrough(self):
        """Dict responses pass through unchanged."""
        data = {"hash": "abc123", "stat": 3}
        result = TorrServer._normalize_json_response(data)
        assert result == data

    def test_list_with_one_element_unwrapped(self):
        """A single-element list is unwrapped to its first element."""
        data = [{"hash": "abc123", "stat": 3}]
        result = TorrServer._normalize_json_response(data)
        assert result == {"hash": "abc123", "stat": 3}

    def test_list_with_multiple_elements_takes_first(self):
        """A multi-element list takes only the first element."""
        data = [{"hash": "abc123"}, {"hash": "def456"}]
        result = TorrServer._normalize_json_response(data)
        assert result == {"hash": "abc123"}

    def test_empty_list_raises_error(self):
        """An empty list raises TorrServerError."""
        with pytest.raises(TorrServerError, match="empty list"):
            TorrServer._normalize_json_response([])

    def test_non_dict_non_list_passthrough(self):
        """Non-dict, non-list values pass through (edge case)."""
        # Strings or numbers should come through as-is; the caller
        # will get a KeyError when accessing ["hash"], which is expected.
        result = TorrServer._normalize_json_response(42)
        assert result == 42


class TestExtractHash:
    """Tests for TorrServer._extract_hash."""

    def test_dict_response_returns_hash(self, torrserver):
        """Standard dict response extracts hash correctly."""
        response = _make_response({"hash": "abc123", "stat": 3})
        result = torrserver._extract_hash(response)
        assert result == "abc123"

    def test_list_response_extracts_hash(self, torrserver):
        """List-wrapped response is unwrapped and hash is extracted."""
        response = _make_response([{"hash": "abc123", "stat": 3}])
        result = torrserver._extract_hash(response)
        assert result == "abc123"

    def test_list_with_multiple_items_takes_first_hash(self, torrserver):
        """Multi-item list takes first element's hash."""
        response = _make_response(
            [{"hash": "first_hash"}, {"hash": "second_hash"}]
        )
        result = torrserver._extract_hash(response)
        assert result == "first_hash"

    def test_empty_list_raises_error(self, torrserver):
        """Empty list response raises TorrServerError."""
        response = _make_response([])
        with pytest.raises(TorrServerError, match="empty list"):
            torrserver._extract_hash(response)

    def test_missing_hash_key_raises_key_error(self, torrserver):
        """Response without 'hash' key raises KeyError."""
        response = _make_response({"stat": 3, "name": "test"})
        with pytest.raises(KeyError):
            torrserver._extract_hash(response)


class TestAddMagnet:
    """Tests for TorrServer.add_magnet with normalized responses."""

    def test_add_magnet_dict_response(self, torrserver):
        """add_magnet handles dict response from TorrServer."""
        torrserver._session.request.return_value = _make_response(
            {"hash": "magnet_hash_1"}
        )
        result = torrserver.add_magnet("magnet:?xt=urn:btih:abc123")
        assert result == "magnet_hash_1"

    def test_add_magnet_list_response(self, torrserver):
        """add_magnet handles list response from TorrServer (issue #193)."""
        torrserver._session.request.return_value = _make_response(
            [{"hash": "magnet_hash_1"}]
        )
        result = torrserver.add_magnet("magnet:?xt=urn:btih:abc123")
        assert result == "magnet_hash_1"


class TestAddTorrentObj:
    """Tests for TorrServer.add_torrent_obj with normalized responses."""

    def test_add_torrent_obj_dict_response(self, torrserver):
        """add_torrent_obj handles dict response from TorrServer."""
        torrserver._session.request.return_value = _make_response(
            {"hash": "torrent_hash_1"}
        )
        mock_file = MagicMock()
        result = torrserver.add_torrent_obj(mock_file)
        assert result == "torrent_hash_1"

    def test_add_torrent_obj_list_response(self, torrserver):
        """add_torrent_obj handles list response from TorrServer (issue #193)."""
        torrserver._session.request.return_value = _make_response(
            [{"hash": "torrent_hash_1"}]
        )
        mock_file = MagicMock()
        result = torrserver.add_torrent_obj(mock_file)
        assert result == "torrent_hash_1"


class TestAddTorrent:
    """Tests for TorrServer.add_torrent with normalized responses."""

    def test_add_torrent_dict_response(self, torrserver, tmp_path):
        """add_torrent handles dict response from TorrServer."""
        torrserver._session.request.return_value = _make_response(
            {"hash": "file_hash_1"}
        )
        torrent_file = tmp_path / "test.torrent"
        torrent_file.write_bytes(b"d8:announce17:http://test.com4:info6:teste")
        result = torrserver.add_torrent(str(torrent_file))
        assert result == "file_hash_1"

    def test_add_torrent_list_response(self, torrserver, tmp_path):
        """add_torrent handles list response from TorrServer (issue #193)."""
        torrserver._session.request.return_value = _make_response(
            [{"hash": "file_hash_1"}]
        )
        torrent_file = tmp_path / "test.torrent"
        torrent_file.write_bytes(b"d8:announce17:http://test.com4:info6:teste")
        result = torrserver.add_torrent(str(torrent_file))
        assert result == "file_hash_1"


class TestGetTorrentInfo:
    """Tests for TorrServer info methods with normalized responses."""

    def test_get_torrent_info_dict(self, torrserver):
        """get_torrent_info handles dict response."""
        expected = {"hash": "abc123", "stat": 3, "file_stats": []}
        torrserver._session.request.return_value = _make_response(expected)
        result = torrserver.get_torrent_info("abc123")
        assert result == expected

    def test_get_torrent_info_list(self, torrserver):
        """get_torrent_info handles list response (defensive)."""
        expected_inner = {"hash": "abc123", "stat": 3, "file_stats": []}
        torrserver._session.request.return_value = _make_response([expected_inner])
        result = torrserver.get_torrent_info("abc123")
        assert result == expected_inner

    def test_torrents_dict(self, torrserver):
        """torrents() handles dict response."""
        expected = {"torrents": []}
        torrserver._session.request.return_value = _make_response(expected)
        result = torrserver.torrents()
        assert result == expected

    def test_torrents_list(self, torrserver):
        """torrents() handles list response (defensive)."""
        expected_inner = {"hash": "abc123"}
        torrserver._session.request.return_value = _make_response([expected_inner])
        result = torrserver.torrents()
        assert result == expected_inner