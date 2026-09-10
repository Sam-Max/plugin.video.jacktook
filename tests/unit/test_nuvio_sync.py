"""Unit tests for the Nuvio library read client (PR slice 1).

These tests mock ``requests`` only; no network access happens. The store,
sync service, view, and wiring are out of scope for this slice.
"""

from unittest.mock import MagicMock

import pytest
import requests

from lib.api.nuvio import (
    LIBRARY_RPC_CURSOR,
    LIBRARY_RPC_DELTA,
    LIBRARY_RPC_SNAPSHOT,
    NuvioClient,
)


def _response(status_code, payload=None, json_error=None):
    response = MagicMock(status_code=status_code)
    if json_error is not None:
        response.json.side_effect = json_error
    else:
        response.json.return_value = payload
    return response


def _client(profile_id=1):
    return NuvioClient(
        access_token="access",
        refresh_token="refresh",
        expires_at="",
        profile_id=profile_id,
    )


def _library_row(**overrides):
    row = {
        "content_id": "tmdb:550",
        "content_type": "movie",
        "name": "Fight Club",
        "poster": "https://image.tmdb.org/t/p/w500/fightclub.jpg",
        "poster_shape": "POSTER",
        "background": "https://image.tmdb.org/t/p/original/fightclub.jpg",
        "description": "An insomniac office worker.",
        "release_info": "1999",
        "imdb_rating": 8.8,
        "genres": ["Drama", "Thriller"],
        "addon_base_url": "https://catalog.example.com",
        "added_at": 1711600000000,
    }
    row.update(overrides)
    return row


def _logged(log):
    return " ".join(str(call) for call in log.call_args_list)


# --- get_library_delta_cursor -------------------------------------------------


def test_get_library_delta_cursor_accepts_zero(monkeypatch):
    post = MagicMock(return_value=_response(200, 0))
    monkeypatch.setattr("lib.api.nuvio.requests.post", post)

    assert _client(profile_id=2).get_library_delta_cursor() == 0

    assert post.call_args.args[0].endswith(f"/rest/v1/rpc/{LIBRARY_RPC_CURSOR}")
    assert post.call_args.kwargs["json"] == {"p_profile_id": 2}


@pytest.mark.parametrize("payload", [True, False, "481", [], {"cursor": 1}, None, 481.0])
def test_get_library_delta_cursor_rejects_non_integer(monkeypatch, payload):
    log = MagicMock()
    monkeypatch.setattr(
        "lib.api.nuvio.requests.post", MagicMock(return_value=_response(200, payload))
    )
    monkeypatch.setattr("lib.api.nuvio.kodilog", log)

    assert _client().get_library_delta_cursor() is None
    assert "invalid_cursor" in _logged(log)


def test_get_library_delta_cursor_none_on_transport_http_and_invalid_json(monkeypatch):
    log = MagicMock()
    monkeypatch.setattr("lib.api.nuvio.kodilog", log)

    monkeypatch.setattr(
        "lib.api.nuvio.requests.post", MagicMock(side_effect=requests.Timeout("private-token"))
    )
    assert _client().get_library_delta_cursor() is None

    monkeypatch.setattr("lib.api.nuvio.requests.post", MagicMock(return_value=_response(500)))
    assert _client().get_library_delta_cursor() is None

    monkeypatch.setattr(
        "lib.api.nuvio.requests.post",
        MagicMock(return_value=_response(200, json_error=ValueError("bad"))),
    )
    assert _client().get_library_delta_cursor() is None

    logged = _logged(log)
    assert "transport" in logged
    assert "http" in logged
    assert "invalid_json" in logged
    assert "private-token" not in logged


def test_get_library_delta_cursor_skips_request_without_a_profile(monkeypatch):
    post = MagicMock()
    monkeypatch.setattr("lib.api.nuvio.requests.post", post)

    assert _client(profile_id="").get_library_delta_cursor() is None
    post.assert_not_called()


# --- get_library --------------------------------------------------------------


def test_get_library_normalizes_rows_and_skips_malformed(monkeypatch):
    payload = [
        _library_row(),
        "not-a-row",
        _library_row(content_id="imdb:tt0137523"),
        _library_row(content_type="person"),
        _library_row(content_id="tmdb:1396", content_type="series", name="Breaking Bad"),
    ]
    monkeypatch.setattr(
        "lib.api.nuvio.requests.post", MagicMock(return_value=_response(200, payload))
    )

    rows = _client().get_library()

    assert [row["tmdb_id"] for row in rows] == [550, 1396]
    assert rows[0] == {
        "content_type": "movie",
        "content_id": "tmdb:550",
        "tmdb_id": 550,
        "title": "Fight Club",
        "poster": "https://image.tmdb.org/t/p/w500/fightclub.jpg",
        "background": "https://image.tmdb.org/t/p/original/fightclub.jpg",
        "description": "An insomniac office worker.",
        "release_info": "1999",
        "imdb_rating": 8.8,
        "genres": ["Drama", "Thriller"],
        "addon_base_url": "https://catalog.example.com",
        "added_at_ms": 1711600000000,
    }


def test_get_library_empty_list_is_a_verified_empty(monkeypatch):
    monkeypatch.setattr("lib.api.nuvio.requests.post", MagicMock(return_value=_response(200, [])))

    assert _client().get_library() == []


@pytest.mark.parametrize(
    "response",
    [
        _response(500),
        _response(200, json_error=ValueError("bad")),
        _response(200, {"rows": []}),
    ],
)
def test_get_library_returns_none_for_http_json_and_non_list(monkeypatch, response):
    monkeypatch.setattr("lib.api.nuvio.requests.post", MagicMock(return_value=response))

    assert _client().get_library() is None


def test_get_library_returns_none_on_transport_failure(monkeypatch):
    monkeypatch.setattr(
        "lib.api.nuvio.requests.post", MagicMock(side_effect=requests.Timeout("private-token"))
    )
    log = MagicMock()
    monkeypatch.setattr("lib.api.nuvio.kodilog", log)

    assert _client().get_library() is None
    assert "transport" in _logged(log)
    assert "private-token" not in _logged(log)


def test_get_library_skips_request_without_a_profile(monkeypatch):
    post = MagicMock()
    monkeypatch.setattr("lib.api.nuvio.requests.post", post)

    assert _client(profile_id="").get_library() is None
    post.assert_not_called()


def test_get_library_forwards_explicit_profile_and_pagination(monkeypatch):
    post = MagicMock(return_value=_response(200, []))
    monkeypatch.setattr("lib.api.nuvio.requests.post", post)

    assert _client(profile_id=1).get_library(profile_id=2, limit=250, offset=500) == []

    assert post.call_args.args[0].endswith(f"/rest/v1/rpc/{LIBRARY_RPC_SNAPSHOT}")
    assert post.call_args.kwargs["json"] == {
        "p_profile_id": 2,
        "p_limit": 250,
        "p_offset": 500,
    }


# --- get_library_delta --------------------------------------------------------


def test_get_library_delta_sorts_events_ascending(monkeypatch):
    payload = [
        _library_row(
            event_id=12, operation="delete", content_id="tmdb:1396", content_type="series"
        ),
        _library_row(event_id=11, operation="upsert"),
    ]
    post = MagicMock(return_value=_response(200, payload))
    monkeypatch.setattr("lib.api.nuvio.requests.post", post)

    events = _client(profile_id=3).get_library_delta(since_event_id=10, limit=500)

    assert [event["event_id"] for event in events] == [11, 12]
    assert [event["operation"] for event in events] == ["upsert", "delete"]
    assert events[0]["tmdb_id"] == 550
    assert post.call_args.args[0].endswith(f"/rest/v1/rpc/{LIBRARY_RPC_DELTA}")
    assert post.call_args.kwargs["json"] == {
        "p_profile_id": 3,
        "p_since_event_id": 10,
        "p_limit": 500,
    }


def test_get_library_delta_skips_malformed_rows(monkeypatch):
    payload = [
        "not-a-row",
        _library_row(event_id=7, operation="upsert", content_id="imdb:tt0137523"),
        _library_row(event_id=8, operation="delete", content_type="person"),
        _library_row(event_id=9, operation="upsert"),
    ]
    monkeypatch.setattr(
        "lib.api.nuvio.requests.post", MagicMock(return_value=_response(200, payload))
    )

    events = _client().get_library_delta()

    assert [event["event_id"] for event in events] == [9]


def test_get_library_delta_drops_events_without_a_positive_event_id(monkeypatch):
    payload = [
        _library_row(event_id=0, operation="upsert"),
        _library_row(operation="delete"),
        _library_row(event_id=5, operation="upsert"),
    ]
    monkeypatch.setattr(
        "lib.api.nuvio.requests.post", MagicMock(return_value=_response(200, payload))
    )

    events = _client().get_library_delta()

    assert [event["event_id"] for event in events] == [5]


def test_get_library_delta_aborts_on_unknown_operation(monkeypatch):
    payload = [
        _library_row(event_id=11, operation="upsert"),
        _library_row(event_id=12, operation="replace"),
    ]
    monkeypatch.setattr(
        "lib.api.nuvio.requests.post", MagicMock(return_value=_response(200, payload))
    )
    log = MagicMock()
    monkeypatch.setattr("lib.api.nuvio.kodilog", log)

    assert _client().get_library_delta() is None
    assert "invalid_operation" in _logged(log)


def test_get_library_delta_empty_list_is_a_verified_empty(monkeypatch):
    monkeypatch.setattr("lib.api.nuvio.requests.post", MagicMock(return_value=_response(200, [])))

    assert _client().get_library_delta() == []


@pytest.mark.parametrize(
    "response",
    [
        _response(500),
        _response(200, json_error=ValueError("bad")),
        _response(200, {"events": []}),
    ],
)
def test_get_library_delta_returns_none_for_http_json_and_non_list(monkeypatch, response):
    monkeypatch.setattr("lib.api.nuvio.requests.post", MagicMock(return_value=response))

    assert _client().get_library_delta() is None


@pytest.mark.parametrize(
    ("requested", "forwarded"),
    [(0, 1), (5000, 1000), (None, 1000), (250, 250)],
)
def test_get_library_delta_clamps_page_limit(monkeypatch, requested, forwarded):
    post = MagicMock(return_value=_response(200, []))
    monkeypatch.setattr("lib.api.nuvio.requests.post", post)

    assert _client().get_library_delta(limit=requested) == []
    assert post.call_args.kwargs["json"]["p_limit"] == forwarded
