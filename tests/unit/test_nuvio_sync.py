"""Unit tests for the Nuvio library read client, SQLite mirror store, and sync service.

These tests mock ``requests`` only; no network access happens and no real
database file is created (the store tests inject a real in-memory connection).
The offline view and its wiring are out of scope for these slices.
"""

import sqlite3
from unittest.mock import MagicMock

import pytest
import requests

from lib.api.nuvio import (
    LIBRARY_RPC_CURSOR,
    LIBRARY_RPC_DELTA,
    LIBRARY_RPC_SNAPSHOT,
    NuvioClient,
)
from lib.api.nuvio_store import (
    NuvioStore,
    invalidate_nuvio_library_cache,
    setup_nuvio_database,
)
from lib.services.nuvio_sync import NuvioSyncService


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


# --- NuvioStore ---------------------------------------------------------------


def _memory_connection():
    """Real in-memory connection; ``sqlite3.connect`` is mocked by conftest."""
    return sqlite3.dbapi2.connect(":memory:")


def _store():
    connection = _memory_connection()
    store = NuvioStore(connection=connection)
    assert store.setup_nuvio_database() is True
    return store


def _event(
    event_id,
    operation="upsert",
    content_type="movie",
    content_id="tmdb:550",
    **overrides,
):
    tmdb_id = int(content_id.split(":", 1)[1]) if content_id.startswith("tmdb:") else None
    event = {
        "content_type": content_type,
        "content_id": content_id,
        "tmdb_id": tmdb_id,
        "title": "Fight Club",
        "poster": "https://image.tmdb.org/t/p/w500/fightclub.jpg",
        "background": "https://image.tmdb.org/t/p/original/fightclub.jpg",
        "description": "An insomniac office worker.",
        "release_info": "1999",
        "imdb_rating": 8.8,
        "genres": ["Drama", "Thriller"],
        "addon_base_url": "https://catalog.example.com",
        "added_at_ms": 1711600000000,
        "event_id": event_id,
        "operation": operation,
    }
    event.update(overrides)
    return event


def _client_item(content_id="tmdb:550", content_type="movie", **overrides):
    item = _event(0, content_type=content_type, content_id=content_id)
    item.pop("event_id", None)
    item.pop("operation", None)
    item.update(overrides)
    return item


def test_store_setup_is_idempotent_and_sets_schema_version():
    connection = _memory_connection()
    store = NuvioStore(connection=connection)

    assert store.setup_nuvio_database() is True
    assert store.setup_nuvio_database() is True

    assert connection.execute("PRAGMA user_version").fetchone()[0] == 1


def test_module_setup_accepts_injected_connection():
    connection = _memory_connection()

    assert setup_nuvio_database(connection) is True
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 1

    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    assert {"nuvio_library", "nuvio_library_meta"} <= tables


def test_store_defaults_meta_and_cursor_when_absent():
    store = _store()

    assert store.count(1) == 0
    assert store.get_cursor_event_id(1) == 0
    assert store.get_meta(1) == {
        "profile_id": 1,
        "cursor_event_id": 0,
        "snapshot_done": 0,
        "last_sync_ms": None,
    }


def test_store_re_sync_is_idempotent_and_refreshes_fields():
    store = _store()

    assert store.apply_delta(1, [_event(event_id=5)], 5) is True
    assert store.apply_delta(1, [_event(event_id=6, title="Fight Club (Updated)")], 6) is True

    items = store.list_items(1, "movie")
    assert store.count(1) == 1
    assert len(items) == 1
    assert items[0]["title"] == "Fight Club (Updated)"
    assert items[0]["last_event_id"] == 6
    assert store.get_cursor_event_id(1) == 6

    # Replaying an already-applied event changes nothing.
    assert store.apply_delta(1, [_event(event_id=5)], 5) is True
    assert store.count(1) == 1
    assert store.get_cursor_event_id(1) == 6


def test_store_applies_out_of_order_events_ascending_with_later_winning():
    store = _store()
    earlier = _event(event_id=11, title="First")
    later = _event(event_id=12, title="Second")

    assert store.apply_delta(1, [later, earlier], 12) is True

    items = store.list_items(1, "movie")
    assert len(items) == 1
    assert items[0]["title"] == "Second"
    assert items[0]["last_event_id"] == 12
    assert store.get_cursor_event_id(1) == 12


def test_store_delete_removes_by_item_key_and_advances_cursor():
    store = _store()
    assert store.apply_delta(1, [_event(event_id=5)], 5) is True
    assert store.count(1) == 1

    assert store.apply_delta(1, [_event(event_id=6, operation="delete")], 6) is True

    assert store.count(1) == 0
    assert store.list_items(1, "movie") == []
    assert store.get_cursor_event_id(1) == 6


def test_store_rolls_back_rows_and_cursor_when_apply_fails():
    store = _store()
    assert store.apply_delta(1, [_event(event_id=5)], 5) is True
    assert store.count(1) == 1

    # An out-of-range SQLite integer on the meta write fails after the delete
    # has executed inside the transaction, forcing a genuine rollback.
    oversized_cursor = 2**63
    assert store.apply_delta(1, [_event(event_id=6, operation="delete")], oversized_cursor) is False

    assert store.count(1) == 1
    assert store.list_items(1, "movie")[0]["tmdb_id"] == 550
    assert store.get_cursor_event_id(1) == 5


def test_store_snapshot_writers_clear_and_finalize():
    store = _store()
    assert store.apply_delta(1, [_event(event_id=5)], 5) is True

    assert store.begin_snapshot(1) is True
    assert store.count(1) == 0
    assert store.get_meta(1)["snapshot_done"] == 0

    items = [
        _client_item(content_id="tmdb:550", content_type="movie"),
        _client_item(content_id="tmdb:1396", content_type="series", title="Breaking Bad"),
    ]
    assert store.write_snapshot_items(1, items) is True
    assert store.count(1) == 2

    assert store.finish_snapshot(1, 10) is True
    meta = store.get_meta(1)
    assert meta["snapshot_done"] == 1
    assert meta["cursor_event_id"] == 10
    assert meta["last_sync_ms"] is not None


def test_store_scopes_rows_by_profile():
    store = _store()

    assert store.apply_delta(1, [_event(event_id=5)], 5) is True
    assert (
        store.apply_delta(
            2,
            [_event(event_id=6, content_id="tmdb:1396", title="Breaking Bad")],
            6,
        )
        is True
    )

    assert store.count(1) == 1
    assert store.count(2) == 1
    assert [item["tmdb_id"] for item in store.list_items(1, "movie")] == [550]
    assert [item["tmdb_id"] for item in store.list_items(2, "movie")] == [1396]
    assert store.get_cursor_event_id(1) == 5
    assert store.get_cursor_event_id(2) == 6


def test_store_list_items_filters_by_content_type():
    store = _store()
    events = [
        _event(event_id=5),
        _event(
            event_id=6,
            content_id="tmdb:1396",
            content_type="series",
            title="Breaking Bad",
        ),
    ]
    assert store.apply_delta(1, events, 6) is True

    assert [item["tmdb_id"] for item in store.list_items(1, "movie")] == [550]
    assert [item["tmdb_id"] for item in store.list_items(1, "series")] == [1396]
    assert store.list_items(1, "person") == []


def test_store_round_trips_genres_and_display_fields():
    store = _store()
    assert store.apply_delta(1, [_event(event_id=5)], 5) is True

    item = store.list_items(1, "movie")[0]
    assert item["genres"] == ["Drama", "Thriller"]
    assert item["title"] == "Fight Club"
    assert item["poster"] == "https://image.tmdb.org/t/p/w500/fightclub.jpg"
    assert item["background"] == "https://image.tmdb.org/t/p/original/fightclub.jpg"
    assert item["description"] == "An insomniac office worker."
    assert item["release_info"] == "1999"
    assert item["imdb_rating"] == 8.8
    assert item["addon_base_url"] == "https://catalog.example.com"
    assert item["added_at_ms"] == 1711600000000


def test_invalidate_nuvio_library_cache_uses_store_prefix(monkeypatch):
    delete_like = MagicMock()
    monkeypatch.setattr("lib.api.nuvio_store.cache", MagicMock(delete_like=delete_like))

    invalidate_nuvio_library_cache()

    delete_like.assert_called_once_with("nuvio.library.%")


# --- NuvioSyncService ---------------------------------------------------------


class _FakeApi:
    """Scriptable stand-in for ``NuvioClient`` that records every call."""

    def __init__(self, profile_id=1, cursor=0):
        self.profile_id = profile_id
        self.cursor = cursor
        self.calls = []
        self.snapshot_responses = []
        self.delta_responses = []

    def get_library_delta_cursor(self, profile_id=None):
        self.calls.append("cursor")
        return self.cursor

    def get_library(self, profile_id=None, limit=500, offset=0):
        self.calls.append(("snapshot", offset))
        if self.snapshot_responses:
            return self.snapshot_responses.pop(0)
        return None

    def get_library_delta(self, profile_id=None, since_event_id=0, limit=1000):
        self.calls.append(("delta", since_event_id))
        if self.delta_responses:
            return self.delta_responses.pop(0)
        return []


class _FakeMonitor:
    def __init__(self, abort=False, wait_returns=False):
        self._abort = abort
        self.wait_returns = wait_returns
        self.wait_calls = []

    def abortRequested(self):
        return self._abort

    def waitForAbort(self, seconds):
        self.wait_calls.append(seconds)
        return self.wait_returns


def _service(api=None, monitor=None, store=None):
    return NuvioSyncService(
        api=api or _FakeApi(),
        monitor=monitor or _FakeMonitor(),
        store=store or _store(),
    )


def test_service_run_returns_immediately_on_abort(monkeypatch):
    monkeypatch.setattr("lib.services.nuvio_sync.is_nuvio_progress_sync_enabled", lambda: True)
    api = _FakeApi()

    _service(api=api, monitor=_FakeMonitor(abort=True)).run()

    assert api.calls == []


def test_service_run_returns_without_requests_when_disabled(monkeypatch):
    monkeypatch.setattr("lib.services.nuvio_sync.is_nuvio_progress_sync_enabled", lambda: False)
    api = _FakeApi()

    _service(api=api).run()

    assert api.calls == []


def test_service_run_skips_cycles_while_services_are_paused(monkeypatch):
    monkeypatch.setattr("lib.services.nuvio_sync.is_nuvio_progress_sync_enabled", lambda: True)
    monkeypatch.setattr("lib.services.nuvio_sync.get_property_no_fallback", lambda _prop: "true")
    api = _FakeApi()
    store = _store()

    _service(api=api, store=store).run()

    assert api.calls == []
    assert store.get_cursor_event_id(1) == 0


def test_service_bootstrap_orders_cursor_snapshot_then_delta():
    api = _FakeApi(profile_id=1, cursor=10)
    api.snapshot_responses = [[_client_item()]]
    api.delta_responses = [[_event(event_id=11)]]
    store = _store()

    _service(api=api, store=store)._bootstrap_if_needed()

    assert api.calls[0] == "cursor"
    assert api.calls[1] == ("snapshot", 0)
    assert api.calls[2] == ("delta", 10)
    meta = store.get_meta(1)
    assert meta["snapshot_done"] == 1
    assert meta["cursor_event_id"] == 11
    assert store.count(1) == 1
    assert store.list_items(1, "movie")[0]["tmdb_id"] == 550


def test_service_bootstrap_pages_snapshot_until_a_short_page(monkeypatch):
    monkeypatch.setattr("lib.services.nuvio_sync.SNAPSHOT_PAGE_LIMIT", 2)
    api = _FakeApi(profile_id=1, cursor=5)
    api.snapshot_responses = [
        [_client_item(content_id="tmdb:550"), _client_item(content_id="tmdb:551")],
        [_client_item(content_id="tmdb:552")],
    ]
    api.delta_responses = [[]]
    store = _store()

    _service(api=api, store=store)._bootstrap_if_needed()

    snapshot_calls = [call for call in api.calls if call[0] == "snapshot"]
    assert snapshot_calls == [("snapshot", 0), ("snapshot", 2)]
    assert store.count(1) == 3


def test_service_bootstrap_retries_when_cursor_unavailable():
    api = _FakeApi(profile_id=1, cursor=None)
    api.snapshot_responses = [[_client_item()]]
    store = _store()
    service = _service(api=api, store=store)

    service._bootstrap_if_needed()

    assert api.calls == ["cursor"]
    assert store.get_meta(1)["snapshot_done"] == 0
    assert store.count(1) == 0

    # Next cycle: the cursor is available, so the snapshot proceeds.
    api.cursor = 7
    api.delta_responses = [[]]
    service._bootstrap_if_needed()

    assert store.get_meta(1)["snapshot_done"] == 1
    assert store.count(1) == 1


def test_service_bootstrap_aborts_when_a_snapshot_page_fails():
    api = _FakeApi(profile_id=1, cursor=3)
    api.snapshot_responses = [None]
    store = _store()

    _service(api=api, store=store)._bootstrap_if_needed()

    meta = store.get_meta(1)
    assert meta["snapshot_done"] == 0
    assert store.count(1) == 0


def test_service_bootstrap_uses_delta_when_snapshot_already_done():
    api = _FakeApi(profile_id=1)
    api.delta_responses = [[_event(event_id=11)]]
    store = _store()
    assert store.finish_snapshot(1, 5) is True

    _service(api=api, store=store)._bootstrap_if_needed()

    assert api.calls == [("delta", 5)]
    assert store.get_cursor_event_id(1) == 11


def test_service_delta_pages_until_a_short_page(monkeypatch):
    monkeypatch.setattr("lib.services.nuvio_sync.DELTA_PAGE_LIMIT", 2)
    api = _FakeApi(profile_id=1)
    api.delta_responses = [
        [_event(event_id=11), _event(event_id=12, content_id="tmdb:552")],
        [_event(event_id=13)],
    ]
    store = _store()

    _service(api=api, store=store)._delta_once()

    delta_calls = [call for call in api.calls if call[0] == "delta"]
    assert delta_calls == [("delta", 0), ("delta", 12)]
    assert store.get_cursor_event_id(1) == 13


def test_service_delta_applies_ascending_and_handles_delete():
    api = _FakeApi(profile_id=1)
    api.delta_responses = [[_event(event_id=12, operation="delete"), _event(event_id=11)]]
    store = _store()

    _service(api=api, store=store)._delta_once()

    assert store.count(1) == 0
    assert store.list_items(1, "movie") == []
    assert store.get_cursor_event_id(1) == 12


def test_service_delta_invalidates_library_cache_on_change(monkeypatch):
    invalidate = MagicMock()
    monkeypatch.setattr("lib.services.nuvio_sync.invalidate_nuvio_library_cache", invalidate)
    api = _FakeApi(profile_id=1)
    api.delta_responses = [[_event(event_id=11)]]

    _service(api=api)._delta_once()

    invalidate.assert_called_once_with()


def test_service_delta_leaves_cache_untouched_without_changes(monkeypatch):
    invalidate = MagicMock()
    monkeypatch.setattr("lib.services.nuvio_sync.invalidate_nuvio_library_cache", invalidate)
    api = _FakeApi(profile_id=1)
    api.delta_responses = [[]]

    _service(api=api)._delta_once()

    invalidate.assert_not_called()


@pytest.mark.parametrize(
    ("configured", "expected_minutes"),
    [(30, 30), (0, 1), (-4, 1), ("bad", 15)],
)
def test_service_clamps_interval_to_at_least_one_minute(monkeypatch, configured, expected_minutes):
    monkeypatch.setattr(
        "lib.services.nuvio_sync.get_setting", lambda _setting_id, _default=None: configured
    )

    assert _service()._get_sync_interval_seconds() == expected_minutes * 60


def test_service_run_bootstraps_then_returns_when_the_waiter_aborts(monkeypatch):
    monkeypatch.setattr("lib.services.nuvio_sync.is_nuvio_progress_sync_enabled", lambda: True)
    monkeypatch.setattr("lib.services.nuvio_sync.get_property_no_fallback", lambda _prop: "")
    monkeypatch.setattr("lib.services.nuvio_sync.get_setting", lambda _id, _default=None: 15)
    api = _FakeApi(profile_id=1, cursor=10)
    api.snapshot_responses = [[_client_item()]]
    api.delta_responses = [[]]
    store = _store()
    monitor = _FakeMonitor(wait_returns=True)

    _service(api=api, monitor=monitor, store=store).run()

    assert store.get_meta(1)["snapshot_done"] == 1
    assert store.count(1) == 1
    assert monitor.wait_calls == [5]
