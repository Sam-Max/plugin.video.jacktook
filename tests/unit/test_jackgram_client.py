from unittest.mock import MagicMock, patch
from urllib.parse import quote

import pytest
import requests

from lib.clients.jackgram.client import Jackgram, _sanitize_url_for_log
from lib.domain.torrent import TorrentStream

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(host="http://example.com", token=None):
    """Create a Jackgram client with a mockable session and notification."""
    mock_notification = MagicMock()
    with patch("lib.clients.base.notification"):
        client = Jackgram(host=host, notification=mock_notification, token=token)
    # Replace the real Session with a MagicMock so no network is used
    client.session = MagicMock()
    client._mock_notification = mock_notification
    return client


def _make_response(json_data=None, status_code=200):
    """Build a MagicMock resembling requests.Response with .json() and .status_code."""
    mock_res = MagicMock()
    mock_res.status_code = status_code
    mock_res.json.return_value = json_data if json_data is not None else {}
    return mock_res


# ---------------------------------------------------------------------------
# search() — endpoint routing
# ---------------------------------------------------------------------------


@patch("lib.clients.jackgram.client.kodilog")
@patch("lib.clients.jackgram.client.translation", return_value="err")
def test_search_tv_with_valid_tmdb_uses_series_endpoint(mock_translation, mock_kodilog):
    client = _make_client()
    mock_res = _make_response(
        {
            "streams": [
                {
                    "title": "Show S01E02",
                    "name": "idx",
                    "size": "1GB",
                    "date": "2024-01-01",
                    "url": "http://x/file",
                    "guid": "g1",
                    "infoHash": "abc",
                }
            ]
        }
    )
    client.session.get.return_value = mock_res

    result = client.search(
        tmdb_id="123", query="anything", mode="tv", media_type="tv", season=1, episode=2
    )

    assert client.session.get.call_count == 1
    called_url = client.session.get.call_args[0][0]
    assert "/stream/series/123:1:2.json" in called_url
    assert len(result) == 1
    assert isinstance(result[0], TorrentStream)
    assert result[0].title == "Show S01E02"


@patch("lib.clients.jackgram.client.kodilog")
@patch("lib.clients.jackgram.client.translation", return_value="err")
def test_search_tv_missing_tmdb_falls_back_to_search(mock_translation, mock_kodilog):
    client = _make_client()
    client.session.get.return_value = _make_response({"results": []})

    # case 1: empty string tmdb_id
    client.search(tmdb_id="", query="my show", mode="tv", media_type="tv", season=1, episode=1)
    url1 = client.session.get.call_args[0][0]
    assert "/search?query=" in url1
    assert "page=1" in url1
    assert "my%20show" in url1
    assert "/stream/series" not in url1

    # case 2: None tmdb_id
    client.search(tmdb_id=None, query="my show", mode="tv", media_type="tv", season=1, episode=1)
    url2 = client.session.get.call_args[0][0]
    assert "/search?query=" in url2
    assert "page=1" in url2

    # case 3: season None
    client.search(
        tmdb_id="123", query="my show", mode="tv", media_type="tv", season=None, episode=1
    )
    url3 = client.session.get.call_args[0][0]
    assert "/search?query=" in url3
    assert "page=1" in url3

    # case 4: episode None
    client.search(
        tmdb_id="123", query="my show", mode="tv", media_type="tv", season=1, episode=None
    )
    url4 = client.session.get.call_args[0][0]
    assert "/search?query=" in url4
    assert "page=1" in url4


@patch("lib.clients.jackgram.client.kodilog")
@patch("lib.clients.jackgram.client.translation", return_value="err")
def test_search_tv_missing_tmdb_falls_back_with_media_type(mock_translation, mock_kodilog):
    """media_type == 'tv' also triggers tv branch even when mode is not 'tv'."""
    client = _make_client()
    client.session.get.return_value = _make_response({"results": []})

    client.search(tmdb_id="", query="fallback", mode="other", media_type="tv", season=1, episode=1)
    url = client.session.get.call_args[0][0]
    assert "/search?query=" in url
    assert "/stream/series" not in url


@patch("lib.clients.jackgram.client.kodilog")
@patch("lib.clients.jackgram.client.translation", return_value="err")
def test_search_movies_missing_tmdb_falls_back_to_search(mock_translation, mock_kodilog):
    client = _make_client()
    client.session.get.return_value = _make_response({"results": []})

    client.search(
        tmdb_id="", query="inception", mode="movies", media_type="movies", season=None, episode=None
    )
    url1 = client.session.get.call_args[0][0]
    assert "/search?query=" in url1
    assert "page=1" in url1
    assert "inception" in url1

    client.search(
        tmdb_id=None,
        query="inception",
        mode="movies",
        media_type="movies",
        season=None,
        episode=None,
    )
    url2 = client.session.get.call_args[0][0]
    assert "/search?query=" in url2
    assert "/stream/movie" not in url2


@patch("lib.clients.jackgram.client.kodilog")
@patch("lib.clients.jackgram.client.translation", return_value="err")
def test_search_movies_with_valid_tmdb_uses_movie_endpoint(mock_translation, mock_kodilog):
    client = _make_client()
    client.session.get.return_value = _make_response(
        {"streams": [{"title": "Movie", "name": "idx", "url": "http://x/file"}]}
    )

    result = client.search(
        tmdb_id="999",
        query="ignored",
        mode="movies",
        media_type="movies",
        season=None,
        episode=None,
    )

    called_url = client.session.get.call_args[0][0]
    assert "/stream/movie/999.json" in called_url
    assert len(result) == 1


@patch("lib.clients.jackgram.client.kodilog")
@patch("lib.clients.jackgram.client.translation", return_value="err")
def test_search_unknown_mode_falls_back_to_search(mock_translation, mock_kodilog):
    client = _make_client()
    client.session.get.return_value = _make_response({"results": []})

    client.search(
        tmdb_id="123",
        query="something",
        mode="other",
        media_type="other",
        season=None,
        episode=None,
    )
    url = client.session.get.call_args[0][0]
    assert "/search?query=" in url
    assert "page=1" in url


@patch("lib.clients.jackgram.client.kodilog")
@patch("lib.clients.jackgram.client.translation", return_value="err")
def test_search_query_with_special_chars_is_quoted(mock_translation, mock_kodilog):
    client = _make_client()
    client.session.get.return_value = _make_response({"results": []})

    query = "a & b/c?"
    expected_encoded = quote(query, safe="")

    client.search(
        tmdb_id="", query=query, mode="other", media_type="other", season=None, episode=None
    )
    called_url = client.session.get.call_args[0][0]
    # Must be percent-encoded, not raw
    assert expected_encoded in called_url
    assert "a & b" not in called_url
    assert "a%20%26%20b" in called_url
    assert "page=1" in called_url

    # verify None query does not crash and encodes as empty
    client.search(
        tmdb_id="", query=None, mode="other", media_type="other", season=None, episode=None
    )
    url_none = client.session.get.call_args[0][0]
    assert "/search?query=&page=1" in url_none


@patch("lib.clients.jackgram.client.kodilog")
@patch("lib.clients.jackgram.client.translation", return_value="err")
@patch("lib.clients.base.notification")
def test_search_status_not_200_returns_empty_list(
    mock_base_notification, mock_translation, mock_kodilog
):
    client = _make_client()
    mock_res = _make_response({"streams": [{"title": "t"}]}, status_code=500)
    client.session.get.return_value = mock_res

    result = client.search(
        tmdb_id="123", query="q", mode="tv", media_type="tv", season=1, episode=1
    )

    assert result == []
    assert result is not None
    # kodilog should have been called for the failure
    assert mock_kodilog.called


@patch("lib.clients.jackgram.client.kodilog")
@patch("lib.clients.jackgram.client.translation", return_value="err")
@patch("lib.clients.base.notification")
def test_search_exception_returns_empty(mock_base_notification, mock_translation, mock_kodilog):
    client = _make_client()
    client.session.get.side_effect = requests.RequestException("network down")

    result = client.search(
        tmdb_id="123", query="q", mode="tv", media_type="tv", season=1, episode=1
    )

    assert result == []
    assert result is not None
    # handle_exception triggers base notification
    assert mock_base_notification.called


@patch("lib.clients.jackgram.client.kodilog")
@patch("lib.clients.jackgram.client.translation", return_value="err")
def test_search_returns_empty_never_none_on_exception_generic(mock_translation, mock_kodilog):
    client = _make_client()
    client.session.get.side_effect = RuntimeError("boom")

    result = client.search(
        tmdb_id="123", query="q", mode="movies", media_type="movies", season=None, episode=None
    )

    assert result == []
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# parse_response()
# ---------------------------------------------------------------------------


def test_parse_response_missing_streams_returns_empty():
    client = _make_client()

    # empty dict
    mock_res = _make_response({})
    assert client.parse_response(mock_res) == []

    # no streams key explicitly
    mock_res2 = MagicMock()
    mock_res2.json.return_value = {"other": 123}
    assert client.parse_response(mock_res2) == []

    # streams is None
    mock_res3 = _make_response({"streams": None})
    # data.get("streams", []) returns None, iterating should yield []
    # original code would fail if streams is None? It does data.get("streams", []) -> None,
    # then for item in None would raise TypeError, but M1 should guard.
    # Check guard: streams is None -> should return []
    # We verify it does not raise and returns []
    try:
        result = client.parse_response(mock_res3)
    except TypeError:
        pytest.fail("parse_response should handle streams=None without TypeError")
    assert result == []

    # streams contains non-dict items should be skipped
    mock_res4 = _make_response({"streams": ["not a dict", 123, None]})
    assert client.parse_response(mock_res4) == []

    # data is not a dict
    mock_res5 = MagicMock()
    mock_res5.json.return_value = []
    assert client.parse_response(mock_res5) == []


def test_parse_response_with_valid_streams_parses():
    # without token — url should remain raw
    client_no_token = _make_client(token=None)
    mock_res = _make_response(
        {
            "streams": [
                {
                    "title": "t",
                    "name": "n",
                    "size": "1GB",
                    "date": "2024-01-01",
                    "url": "http://x/file",
                    "guid": "",
                    "infoHash": "",
                }
            ]
        }
    )
    result = client_no_token.parse_response(mock_res)
    assert len(result) == 1
    ts = result[0]
    assert isinstance(ts, TorrentStream)
    assert ts.title == "t"
    assert ts.indexer == "n"
    assert ts.size == "1GB"
    assert ts.publishDate == "2024-01-01"
    assert ts.url == "http://x/file"
    assert "|Authorization" not in ts.url
    assert ts.type == "Direct"

    # M2: client returns clean URL; token injected only in resolve_playback_url
    client_with_token = _make_client(token="secret123")
    mock_res2 = _make_response(
        {
            "streams": [
                {
                    "title": "t",
                    "name": "n",
                    "size": "1GB",
                    "date": "2024-01-01",
                    "url": "http://x/file",
                    "guid": "g1",
                    "infoHash": "hash1",
                    "seeders": 5,
                    "languages": ["en"],
                    "fullLanguages": "English",
                    "provider": "p1",
                    "peers": 10,
                }
            ]
        }
    )
    result2 = client_with_token.parse_response(mock_res2)
    assert len(result2) == 1
    ts2 = result2[0]
    assert ts2.url == "http://x/file"
    assert "|Authorization" not in ts2.url
    assert ts2.guid == "g1"
    assert ts2.infoHash == "hash1"
    assert ts2.seeders == 5
    assert ts2.peers == 10
    assert ts2.languages == ["en"]
    assert ts2.fullLanguages == "English"
    assert ts2.provider == "p1"

    # empty url should not append token
    mock_res3 = _make_response({"streams": [{"title": "t", "url": ""}]})
    result3 = client_with_token.parse_response(mock_res3)
    assert result3[0].url == ""


def test_parse_response_accepts_plain_dict_without_json_method():
    client = _make_client(token=None)
    plain_dict = {"streams": [{"title": "plain", "name": "idx", "url": "http://x/f"}]}
    result = client.parse_response(plain_dict)
    assert len(result) == 1
    assert result[0].title == "plain"


# ---------------------------------------------------------------------------
# parse_response_search()
# ---------------------------------------------------------------------------


def test_parse_response_search_missing_results_returns_empty():
    client = _make_client()

    assert client.parse_response_search(_make_response({})) == []
    assert client.parse_response_search(_make_response({"results": None})) == []
    assert client.parse_response_search(_make_response({"other": []})) == []

    # results is not a list -> guarded
    mock_res = _make_response({"results": "not a list"})
    assert client.parse_response_search(mock_res) == []

    # data is not a dict
    mock_res2 = MagicMock()
    mock_res2.json.return_value = []
    assert client.parse_response_search(mock_res2) == []


def test_parse_response_search_file_type_and_nested_files():
    # test both branches: type == "file" direct, and else with files[]
    client = _make_client(token=None)
    mock_res = _make_response(
        {
            "results": [
                {
                    "type": "file",
                    "title": "direct file",
                    "name": "idx1",
                    "size": "500MB",
                    "date": "2024-02-02",
                    "url": "http://x/direct",
                },
                {
                    "type": "folder",
                    "files": [
                        {
                            "title": "nested1",
                            "name": "idx2",
                            "size": "700MB",
                            "date": "2024-03-03",
                            "url": "http://x/nested1",
                        },
                        {
                            "title": "nested2",
                            "name": "idx3",
                            "size": "800MB",
                            "date": "2024-04-04",
                            "url": "http://x/nested2",
                        },
                    ],
                },
            ]
        }
    )
    result = client.parse_response_search(mock_res)
    assert len(result) == 3
    assert result[0].title == "direct file"
    assert result[0].indexer == "idx1"
    assert result[0].url == "http://x/direct"
    assert result[1].title == "nested1"
    assert result[2].title == "nested2"
    for ts in result:
        assert ts.type == "Direct"

    # M2: client returns clean URLs; token injected only in resolve_playback_url
    client_tok = _make_client(token="tok123")
    result_tok = client_tok.parse_response_search(mock_res)
    assert result_tok[0].url == "http://x/direct"
    assert result_tok[1].url == "http://x/nested1"
    assert "|Authorization" not in result_tok[0].url
    assert "|Authorization" not in result_tok[1].url

    # files is not a list -> should be skipped gracefully
    mock_res_bad = _make_response({"results": [{"type": "folder", "files": "bad"}]})
    assert client.parse_response_search(mock_res_bad) == []

    # non-dict items should be skipped
    mock_res_mixed = _make_response(
        {
            "results": [
                "not a dict",
                {"type": "file", "title": "ok", "url": "http://x/ok"},
            ]
        }
    )
    res_mixed = client.parse_response_search(mock_res_mixed)
    assert len(res_mixed) == 1
    assert res_mixed[0].title == "ok"


def test_parse_response_search_plain_dict_without_json():
    client = _make_client()
    plain = {"results": [{"type": "file", "title": "plain", "url": "http://x/p"}]}
    result = client.parse_response_search(plain)
    assert len(result) == 1
    assert result[0].title == "plain"


# ---------------------------------------------------------------------------
# _extract_file_info()
# ---------------------------------------------------------------------------


def test_extract_file_info_non_dict_returns_defaults():
    client = _make_client(token=None)

    result = client._extract_file_info("not a dict")
    assert result["title"] == ""
    assert result["type"] == "Direct"
    assert result["indexer"] == ""
    assert result["size"] == ""
    assert result["publishDate"] == ""
    assert result["url"] == ""

    result2 = client._extract_file_info(None)
    assert result2["title"] == ""

    result3 = client._extract_file_info(12345)
    assert result3["url"] == ""


def test_extract_file_info_with_valid_dict():
    client = _make_client(token=None)
    file_dict = {
        "title": "my file",
        "name": "my indexer",
        "size": "1GB",
        "date": "2024-05-05",
        "url": "http://x/file",
    }
    result = client._extract_file_info(file_dict)
    assert result["title"] == "my file"
    assert result["indexer"] == "my indexer"
    assert result["size"] == "1GB"
    assert result["publishDate"] == "2024-05-05"
    assert result["url"] == "http://x/file"
    assert result["type"] == "Direct"


def test_extract_file_info_token_appended():
    # M2: client returns clean URL; token injected only in resolve_playback_url
    client = _make_client(token="mytoken")
    file_dict = {"title": "t", "url": "http://x/file"}
    result = client._extract_file_info(file_dict)
    assert result["url"] == "http://x/file"
    assert "|Authorization" not in result["url"]

    # empty url stays empty even with token
    file_dict_empty = {"title": "t", "url": ""}
    result2 = client._extract_file_info(file_dict_empty)
    assert result2["url"] == ""

    # token None still returns clean URL
    client_no_tok = _make_client(token=None)
    result3 = client_no_tok._extract_file_info(file_dict)
    assert result3["url"] == "http://x/file"


# ---------------------------------------------------------------------------
# _sanitize_url_for_log()
# ---------------------------------------------------------------------------


def test_sanitize_url_for_log_hides_token():
    secret = "http://x/file|Authorization=Bearer secret123"
    sanitized = _sanitize_url_for_log(secret)
    assert "secret123" not in sanitized
    assert sanitized == "http://x/file|Authorization=Bearer ***"
    assert "***" in sanitized

    # without pipe stays identical
    plain = "http://x/file"
    assert _sanitize_url_for_log(plain) == plain

    # without Bearer inside pipe — unchanged
    other = "http://x/file|Other=123"
    assert _sanitize_url_for_log(other) == other

    # empty string
    assert _sanitize_url_for_log("") == ""


@patch("lib.clients.jackgram.client.kodilog")
@patch("lib.clients.jackgram.client.translation", return_value="err")
def test_kodilog_never_logs_raw_token(mock_translation, mock_kodilog):
    token = "supersecrettoken999"
    client = _make_client(token=token)
    client.session.get.return_value = _make_response({"streams": []})

    # trigger search that will log the URL (via kodilog)
    client.search(
        tmdb_id="123", query="test", mode="movies", media_type="movies", season=None, episode=None
    )

    # also trigger a failed status path
    client.session.get.return_value = _make_response({}, status_code=500)
    client.search(tmdb_id="123", query="test", mode="tv", media_type="tv", season=1, episode=1)

    # collect all kodilog call args
    all_calls = " ".join(str(call) for call in mock_kodilog.call_args_list)
    # raw token must never appear in any log call
    assert token not in all_calls
    # if the URL contained the token pipe, it should be sanitized with ***
    # search URLs themselves do not contain token, but direct stream URLs could
    # Ensure no raw token leaked
    for call in mock_kodilog.call_args_list:
        args, _ = call
        for arg in args:
            assert token not in str(arg)


@patch("lib.clients.jackgram.client.kodilog")
@patch("lib.clients.jackgram.client.translation", return_value="err")
def test_host_trailing_slash_does_not_double_slash(mock_translation, mock_kodilog):
    client = _make_client(host="http://example.com/")
    client.session.get.return_value = _make_response({"streams": []})
    client.search(
        tmdb_id="123", query="q", mode="movies", media_type="movies", season=None, episode=None
    )
    called_url = client.session.get.call_args[0][0]
    assert "http://example.com/stream/movie/123.json" in called_url
    assert "http://example.com//stream" not in called_url


# ---------------------------------------------------------------------------
# M2 contract: client returns clean URLs — token only in resolve_playback_url
# ---------------------------------------------------------------------------


def test_parse_response_does_not_inject_token_even_when_token_set():
    client = _make_client(token="tok123")
    mock_res = _make_response({"streams": [{"title": "t", "name": "n", "url": "http://x/file"}]})
    result = client.parse_response(mock_res)
    assert len(result) == 1
    assert result[0].url == "http://x/file"
    assert "|Authorization" not in result[0].url


def test_extract_file_info_does_not_inject_token():
    client = _make_client(token="tok123")
    result = client._extract_file_info({"title": "t", "url": "http://x/file"})
    assert result["url"] == "http://x/file"
    assert "|Authorization" not in result["url"]


@patch("lib.utils.player.utils.get_setting", return_value="tok123")
def test_resolve_playback_url_injects_token_once(mock_get_setting):
    from lib.utils.player.utils import resolve_playback_url

    data = {"type": "Direct", "indexer": "Jackgram", "url": "http://x/file"}
    result = resolve_playback_url(data)
    assert result is not None
    assert result["url"] == "http://x/file|Authorization=Bearer tok123"
    mock_get_setting.assert_called_with("jackgram_token", "")


@patch("lib.utils.player.utils.get_setting", return_value="tok123")
def test_resolve_playback_url_idempotent_no_double_injection(mock_get_setting):
    from lib.utils.player.utils import resolve_playback_url

    data = {
        "type": "Direct",
        "indexer": "Jackgram",
        "url": "http://x/file|Authorization=Bearer tok123",
    }
    result = resolve_playback_url(data)
    assert result is not None
    assert result["url"] == "http://x/file|Authorization=Bearer tok123"
    # must not duplicate
    assert result["url"].count("|Authorization=Bearer") == 1


@patch("lib.utils.player.utils.get_setting", return_value="")
def test_resolve_playback_url_no_injection_when_token_empty(mock_get_setting):
    from lib.utils.player.utils import resolve_playback_url

    data = {"type": "Direct", "indexer": "Jackgram", "url": "http://x/file"}
    result = resolve_playback_url(data)
    assert result is not None
    assert result["url"] == "http://x/file"
    assert "|Authorization" not in result["url"]


@patch("lib.clients.jackgram.utils.kodilog")
@patch("lib.clients.jackgram.utils.translation", side_effect=lambda string_id: f"{string_id}")
@patch("lib.clients.jackgram.utils.notification")
@patch("lib.clients.jackgram.utils.Jackgram")
@patch("lib.clients.jackgram.utils.validate_host", return_value=True)
@patch("lib.clients.jackgram.utils.get_setting")
def test_jackgram_connection_notifies_success_on_200(
    mock_get_setting,
    mock_validate_host,
    mock_jackgram,
    mock_notification,
    mock_translation,
    mock_kodilog,
):
    from lib.clients.jackgram.utils import test_jackgram_connection

    mock_get_setting.side_effect = lambda key, default=None: {
        "jackgram_host": "http://example.com/",
        "jackgram_token": "token",
    }.get(key, default)
    mock_jackgram.return_value.session.get.return_value = _make_response(status_code=200)

    test_jackgram_connection({})

    mock_translation.assert_called_once_with(30260)
    mock_notification.assert_called_once_with("30260")
    mock_jackgram.return_value.session.get.assert_called_once_with(
        "http://example.com/status",
        headers={"Authorization": "Bearer token"},
        timeout=(5, 15),
    )
    mock_kodilog.assert_not_called()


@patch("lib.clients.jackgram.utils.kodilog")
@patch("lib.clients.jackgram.utils.translation", side_effect=lambda string_id: f"{string_id}")
@patch("lib.clients.jackgram.utils.notification")
@patch("lib.clients.jackgram.utils.Jackgram")
@patch("lib.clients.jackgram.utils.validate_host", return_value=True)
@patch("lib.clients.jackgram.utils.get_setting", return_value="http://example.com")
def test_jackgram_connection_notifies_unauthorized_on_401(
    mock_get_setting,
    mock_validate_host,
    mock_jackgram,
    mock_notification,
    mock_translation,
    mock_kodilog,
):
    from lib.clients.jackgram.utils import test_jackgram_connection

    mock_jackgram.return_value.session.get.return_value = _make_response(status_code=401)

    test_jackgram_connection({})

    mock_translation.assert_called_once_with(30221)
    mock_notification.assert_called_once_with("30221: Jackgram")
    mock_kodilog.assert_not_called()


@patch("lib.clients.jackgram.utils.kodilog")
@patch("lib.clients.jackgram.utils.translation", side_effect=lambda string_id: f"{string_id}")
@patch("lib.clients.jackgram.utils.notification")
@patch("lib.clients.jackgram.utils.Jackgram")
@patch("lib.clients.jackgram.utils.validate_host", return_value=True)
@patch("lib.clients.jackgram.utils.get_setting", return_value="http://example.com")
def test_jackgram_connection_notifies_and_logs_request_errors(
    mock_get_setting,
    mock_validate_host,
    mock_jackgram,
    mock_notification,
    mock_translation,
    mock_kodilog,
):
    from lib.clients.jackgram.utils import test_jackgram_connection

    mock_jackgram.return_value.session.get.side_effect = requests.RequestException("network down")

    test_jackgram_connection({})

    mock_translation.assert_called_once_with(30261)
    mock_notification.assert_called_once_with("30261")
    mock_kodilog.assert_called_once_with("Jackgram test connection failed: network down")


@patch("lib.clients.jackgram.utils.kodilog")
@patch("lib.clients.jackgram.utils.translation")
@patch("lib.clients.jackgram.utils.notification")
@patch("lib.clients.jackgram.utils.Jackgram")
@patch("lib.clients.jackgram.utils.validate_host", return_value=False)
@patch("lib.clients.jackgram.utils.get_setting", return_value="invalid-host")
def test_jackgram_connection_does_not_request_an_invalid_host(
    mock_get_setting,
    mock_validate_host,
    mock_jackgram,
    mock_notification,
    mock_translation,
    mock_kodilog,
):
    from lib.clients.jackgram.utils import test_jackgram_connection

    test_jackgram_connection({})

    mock_jackgram.assert_not_called()
    mock_notification.assert_not_called()
    mock_kodilog.assert_not_called()


# ---------------------------------------------------------------------------
# process_results pagination thresholds (raw_files=11, latest=12)
# ---------------------------------------------------------------------------


def _make_raw_items(n):
    return [{"date": f"2024-01-{i + 1:02d}", "file_name": f"file{i}.mkv"} for i in range(n)]


def _make_title_items(n):
    return [
        {"date": f"2024-01-{i + 1:02d}", "type": "movie", "tmdb_id": i, "title": f"Title {i}"}
        for i in range(n)
    ]


def test_process_results_raw_files_with_11_shows_next():
    from lib.clients.jackgram.utils import add_jackgram_raw_file_item, process_results

    items = _make_raw_items(11)
    with patch("lib.clients.jackgram.utils.execute_thread_pool") as mock_pool, patch(
        "lib.clients.jackgram.utils.add_next_button"
    ) as mock_next, patch("lib.clients.jackgram.utils.end_of_directory") as mock_eod, patch(
        "lib.clients.jackgram.utils.apply_section_view"
    ) as mock_view, patch("lib.clients.jackgram.utils.kodilog"):
        process_results(items, add_jackgram_raw_file_item, "list_jackgram_raw_files", 1)

        mock_pool.assert_called_once()
        mock_next.assert_called_once_with("list_jackgram_raw_files", page=1)
        assert mock_eod.called
        mock_view.assert_called_once()


def test_process_results_raw_files_with_10_no_next():
    from lib.clients.jackgram.utils import add_jackgram_raw_file_item, process_results

    items = _make_raw_items(10)
    with patch("lib.clients.jackgram.utils.execute_thread_pool") as mock_pool, patch(
        "lib.clients.jackgram.utils.add_next_button"
    ) as mock_next, patch("lib.clients.jackgram.utils.end_of_directory"), patch(
        "lib.clients.jackgram.utils.apply_section_view"
    ), patch("lib.clients.jackgram.utils.kodilog"):
        process_results(items, add_jackgram_raw_file_item, "list_jackgram_raw_files", 3)

        mock_pool.assert_called_once()
        mock_next.assert_not_called()


def test_process_results_latest_with_12_shows_next():
    from lib.clients.jackgram.utils import add_jackgram_title_item, process_results

    items = _make_title_items(12)
    with patch("lib.clients.jackgram.utils.execute_thread_pool") as mock_pool, patch(
        "lib.clients.jackgram.utils.add_next_button"
    ) as mock_next, patch("lib.clients.jackgram.utils.end_of_directory"), patch(
        "lib.clients.jackgram.utils.apply_section_view"
    ), patch("lib.clients.jackgram.utils.kodilog"):
        process_results(items, add_jackgram_title_item, "list_jackgram_latest_movies", 2)

        mock_pool.assert_called_once()
        mock_next.assert_called_once_with("list_jackgram_latest_movies", page=2)


def test_process_results_latest_with_11_no_next():
    from lib.clients.jackgram.utils import add_jackgram_title_item, process_results

    items = _make_title_items(11)
    with patch("lib.clients.jackgram.utils.execute_thread_pool") as mock_pool, patch(
        "lib.clients.jackgram.utils.add_next_button"
    ) as mock_next, patch("lib.clients.jackgram.utils.end_of_directory"), patch(
        "lib.clients.jackgram.utils.apply_section_view"
    ), patch("lib.clients.jackgram.utils.kodilog"):
        process_results(items, add_jackgram_title_item, "list_jackgram_latest_series", 1)

        mock_pool.assert_called_once()
        mock_next.assert_not_called()


def test_process_results_empty_and_none_no_next():
    from lib.clients.jackgram.utils import add_jackgram_raw_file_item, process_results

    with patch("lib.clients.jackgram.utils.execute_thread_pool") as mock_pool, patch(
        "lib.clients.jackgram.utils.add_next_button"
    ) as mock_next, patch("lib.clients.jackgram.utils.end_of_directory") as mock_eod, patch(
        "lib.clients.jackgram.utils.apply_section_view"
    ) as mock_view, patch("lib.clients.jackgram.utils.kodilog") as mock_log:
        process_results([], add_jackgram_raw_file_item, "list_jackgram_raw_files", 1)
        mock_next.assert_not_called()
        mock_pool.assert_not_called()
        mock_eod.assert_called_once()
        mock_view.assert_not_called()
        assert mock_log.called

        mock_pool.reset_mock()
        mock_next.reset_mock()
        mock_eod.reset_mock()
        mock_view.reset_mock()
        mock_log.reset_mock()

        process_results(None, add_jackgram_raw_file_item, "list_jackgram_raw_files", 1)
        mock_next.assert_not_called()
        mock_pool.assert_not_called()
        mock_eod.assert_called_once()
        mock_view.assert_not_called()

    from lib.clients.jackgram.utils import add_jackgram_title_item

    with patch("lib.clients.jackgram.utils.execute_thread_pool") as mock_pool2, patch(
        "lib.clients.jackgram.utils.add_next_button"
    ) as mock_next2, patch("lib.clients.jackgram.utils.end_of_directory") as mock_eod2, patch(
        "lib.clients.jackgram.utils.apply_section_view"
    ), patch("lib.clients.jackgram.utils.kodilog"):
        process_results([], add_jackgram_title_item, "list_jackgram_latest_movies", 1)
        mock_next2.assert_not_called()
        mock_pool2.assert_not_called()
        mock_eod2.assert_called_once()


def test_process_results_latest_dedupe_can_suppress_next():
    from lib.clients.jackgram.utils import add_jackgram_title_item, process_results

    dup_items = [
        {"date": f"2024-01-{i + 1:02d}", "type": "movie", "tmdb_id": 1, "title": f"Title {i}"}
        for i in range(12)
    ]
    with patch("lib.clients.jackgram.utils.execute_thread_pool") as mock_pool, patch(
        "lib.clients.jackgram.utils.add_next_button"
    ) as mock_next, patch("lib.clients.jackgram.utils.end_of_directory"), patch(
        "lib.clients.jackgram.utils.apply_section_view"
    ), patch("lib.clients.jackgram.utils.kodilog"):
        process_results(dup_items, add_jackgram_title_item, "list_jackgram_latest_movies", 1)

        mock_pool.assert_called_once()
        mock_next.assert_not_called()


# ---------------------------------------------------------------------------
# Search in Telegram — client-side title filtering
# ---------------------------------------------------------------------------


def _search_payload_mixed():
    return {
        "results": [
            {
                "type": "file",
                "title": "Love Story 1080p BluRay",
                "name": "idx",
                "url": "http://x/love1",
            },
            {
                "type": "file",
                "title": "The Witcher S03E01 1080p",
                "name": "idx",
                "url": "http://x/witcher",
            },
            {
                "type": "file",
                "title": "Random Movie 720p",
                "name": "idx",
                "url": "http://x/random",
            },
        ]
    }


@patch("lib.clients.jackgram.client.kodilog")
@patch("lib.clients.jackgram.client.translation", return_value="err")
def test_search_filters_query_endpoint_results_by_all_case_insensitive_terms(
    mock_translation, mock_kodilog
):
    client = _make_client()
    client.session.get.return_value = _make_response(_search_payload_mixed())
    result = client.search(
        tmdb_id="",
        query=" LOVE   story ",
        mode="other",
        media_type="other",
        season=None,
        episode=None,
    )
    assert [stream.title for stream in result] == ["Love Story 1080p BluRay"]
