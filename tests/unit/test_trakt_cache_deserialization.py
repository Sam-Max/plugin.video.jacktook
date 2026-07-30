import json
import os
from unittest.mock import MagicMock, patch

import pytest

from lib.api.trakt.trakt_cache import (
    MAX_TRAKT_JSON_ROW_SIZE,
    MAX_TRAKT_LEGACY_LITERAL_SIZE,
    TraktCache,
    cache_trakt_object,
    default_activities,
    get_activity,
    set_activity,
)
from lib.services.trakt_sync import TraktSyncService


def database_with_row(value):
    database = MagicMock()
    database.execute.return_value.fetchone.return_value = (value,)
    return database


class MemoryDatabase:
    def __init__(self, storage):
        self.storage = storage
        self._selected_key = None

    def execute(self, command, args=()):
        if command.startswith("SELECT"):
            self._selected_key = args[0]
        elif command.startswith("INSERT"):
            self.storage[args[0]] = args[1]
        return self

    def fetchone(self):
        value = self.storage.get(self._selected_key)
        return (value,) if value is not None else None


def normalized_list_rows():
    return [
        {
            "name": f"List {index}",
            "description": "x" * 180,
            "slug": f"list-{index}",
            "trakt_id": index,
            "username": "tester",
            "item_count": index,
            "privacy": "public",
            "with_auth": True,
        }
        for index in range(1_000)
    ]


def test_valid_legacy_repr_cache_row_decodes():
    database = database_with_row(repr([{"id": 1}, {"id": 2}]))
    with patch("lib.api.trakt.trakt_cache.connect_database", return_value=database):
        result = TraktCache().get("legacy-list", list)

    assert result == [{"id": 1}, {"id": 2}]


def test_valid_legacy_repr_activity_row_decodes():
    activity = default_activities()
    database = database_with_row(repr(activity))
    with patch("lib.api.trakt.trakt_cache.connect_database", return_value=database):
        result = get_activity()

    assert result == activity


def test_valid_legacy_paginated_cache_row_decodes():
    cached = ([{"title": "Item"}], {"X-Pagination-Page": 1})
    database = database_with_row(repr(cached))
    with patch("lib.api.trakt.trakt_cache.connect_database", return_value=database):
        result = TraktCache().get("paginated-list", tuple)

    assert result == cached


def test_representative_thousand_row_json_cache_round_trips():
    rows = normalized_list_rows()
    storage = {}
    database = MemoryDatabase(storage)
    with patch("lib.api.trakt.trakt_cache.connect_database", return_value=database):
        TraktCache().set("large-list", rows)
        result = TraktCache().get("large-list", list, item_type=dict)

    encoded_size = len(storage["large-list"].encode("utf-8"))
    assert MAX_TRAKT_LEGACY_LITERAL_SIZE < encoded_size < MAX_TRAKT_JSON_ROW_SIZE
    assert result == rows


def test_json_pagination_array_restores_tuple_contract():
    cached = ([{"title": "Item"}], {"X-Pagination-Page": 1})
    storage = {}
    database = MemoryDatabase(storage)
    with patch("lib.api.trakt.trakt_cache.connect_database", return_value=database):
        TraktCache().set("paginated-list", cached)
        result = TraktCache().get("paginated-list", tuple)

    assert json.loads(storage["paginated-list"]) == [cached[0], cached[1]]
    assert result == cached
    assert isinstance(result, tuple)


@pytest.mark.parametrize(
    ("raw_value", "expected_type"),
    [
        ("not valid Python", list),
        (repr({"wrong": "type"}), list),
        (repr(([],)), tuple),
        (repr(({}, None)), tuple),
        (repr(([1], {})), tuple),
    ],
)
def test_malformed_or_wrong_type_cache_rows_are_cache_misses(raw_value, expected_type):
    database = database_with_row(raw_value)
    with patch("lib.api.trakt.trakt_cache.connect_database", return_value=database), patch(
        "lib.api.trakt.trakt_cache.kodilog"
    ) as log:
        result = TraktCache().get("corrupt-row", expected_type)

    assert result is None
    log.assert_called_once()


def test_wrong_list_item_type_is_a_cache_miss():
    database = database_with_row(repr([{"expected": "mapping"}, 2]))
    with patch("lib.api.trakt.trakt_cache.connect_database", return_value=database):
        result = TraktCache().get("wrong-item-row", list, item_type=dict)

    assert result is None


def test_executable_cache_payload_is_never_executed():
    payload = "__import__('os').system('should-not-run')"
    database = database_with_row(payload)
    with patch("lib.api.trakt.trakt_cache.connect_database", return_value=database), patch.object(
        os, "system"
    ) as system:
        result = TraktCache().get("executable-row", list)

    assert result is None
    system.assert_not_called()


def test_oversized_cache_row_is_rejected_before_parsing():
    payload = repr(["x" * MAX_TRAKT_LEGACY_LITERAL_SIZE])
    database = database_with_row(payload)
    with patch("lib.api.trakt.trakt_cache.connect_database", return_value=database), patch(
        "lib.api.trakt.trakt_cache.ast.literal_eval"
    ) as literal_eval, patch("lib.api.trakt.trakt_cache.kodilog") as log:
        result = TraktCache().get("oversized-row", list)

    assert result is None
    literal_eval.assert_not_called()
    assert log.call_args.args[0] == "Oversized legacy Trakt cache row ignored: oversized-row"


def test_oversized_json_row_is_rejected_before_parsing():
    payload = json.dumps(["x" * MAX_TRAKT_JSON_ROW_SIZE])
    database = database_with_row(payload)
    with patch("lib.api.trakt.trakt_cache.connect_database", return_value=database), patch(
        "lib.api.trakt.trakt_cache.json.loads"
    ) as json_loads, patch("lib.api.trakt.trakt_cache.ast.literal_eval") as literal_eval:
        result = TraktCache().get("oversized-json", list)

    assert result is None
    json_loads.assert_not_called()
    literal_eval.assert_not_called()


def test_oversized_legacy_row_misses_once_then_rewrites_as_json():
    rows = normalized_list_rows()
    legacy = repr(rows)
    assert MAX_TRAKT_LEGACY_LITERAL_SIZE < len(legacy) < MAX_TRAKT_JSON_ROW_SIZE
    storage = {"large-list": legacy}
    database = MemoryDatabase(storage)
    fetch = MagicMock(return_value=rows)

    with patch("lib.api.trakt.trakt_cache.connect_database", return_value=database):
        first = cache_trakt_object(fetch, "large-list", None, list, item_type=dict)
        second = cache_trakt_object(fetch, "large-list", None, list, item_type=dict)

    assert first == rows
    assert second == rows
    fetch.assert_called_once_with(None)
    assert json.loads(storage["large-list"]) == rows


def test_oversized_value_is_not_written():
    database = MagicMock()
    value = [{"payload": "x" * MAX_TRAKT_JSON_ROW_SIZE}]
    with patch("lib.api.trakt.trakt_cache.connect_database", return_value=database), patch(
        "lib.api.trakt.trakt_cache.kodilog"
    ) as log:
        TraktCache().set("oversized-write", value)

    database.execute.assert_not_called()
    log.assert_called_once_with("Oversized Trakt cache value not written: oversized-write")


def test_activity_write_uses_json():
    database = MagicMock()
    activity = default_activities()
    with patch("lib.api.trakt.trakt_cache.connect_database", return_value=database):
        set_activity(activity)

    encoded = database.execute.call_args.args[1][1]
    assert json.loads(encoded) == activity


@pytest.mark.parametrize("raw_value", ["broken {", repr([]), repr("wrong")])
def test_corrupt_activity_rows_return_fresh_defaults(raw_value):
    database = database_with_row(raw_value)
    with patch("lib.api.trakt.trakt_cache.connect_database", return_value=database):
        result = get_activity()

    assert result == default_activities()
    assert result is not default_activities()


@pytest.mark.parametrize(
    "invalid_activity",
    [
        {"movies": []},
        {"movies": {"watched_at": 123}},
        {"all": "timestamp"},
    ],
)
def test_nested_invalid_activity_rows_return_fresh_defaults(invalid_activity):
    database = database_with_row(repr(invalid_activity))
    with patch("lib.api.trakt.trakt_cache.connect_database", return_value=database):
        result = get_activity()

    assert result == default_activities()


@pytest.mark.parametrize("invalid_value", [[], {"watched_at": 123}])
def test_complete_activity_with_invalid_nested_shape_uses_defaults(invalid_value):
    activity = default_activities()
    activity["movies"] = invalid_value
    database = database_with_row(repr(activity))
    with patch("lib.api.trakt.trakt_cache.connect_database", return_value=database):
        result = get_activity()

    assert result == default_activities()


def test_harmless_extra_activity_keys_are_preserved():
    activity = default_activities()
    activity["future_section"] = {"updated_at": "2026-07-30T00:00:00.000Z"}
    database = database_with_row(repr(activity))
    with patch("lib.api.trakt.trakt_cache.connect_database", return_value=database):
        result = get_activity()

    assert result == activity


def test_activity_sync_recovers_from_nested_invalid_checkpoint():
    database = database_with_row(repr({"movies": []}))
    api = MagicMock()
    latest = default_activities()
    latest["movies"]["watched_at"] = "2026-07-30T00:00:00.000Z"
    api.sync.get_last_activities.return_value = latest
    service = TraktSyncService(api=api, monitor=MagicMock())

    with patch("lib.api.trakt.trakt_cache.connect_database", return_value=database), patch.object(
        service, "_apply_activity_changes"
    ) as apply_changes, patch("lib.services.trakt_sync.set_activity") as set_activity:
        result = service.sync_activities()

    assert "watched_movies" in result
    apply_changes.assert_called_once()
    set_activity.assert_called_once_with(latest)
