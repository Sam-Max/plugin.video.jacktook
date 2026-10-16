import copy
from datetime import timedelta
from unittest.mock import MagicMock, call, patch

import pytest

from lib.clients.debrid import torbox

READY = {
    "id": 7,
    "download_finished": True,
    "download_present": True,
    "files": [
        {"id": 1, "name": "Show.S01E01.mkv", "size": 100},
        {"id": 2, "name": "Show.S01E02.mkv", "size": 200},
    ],
}


@pytest.fixture
def metadata_cache():
    now = [0]
    entries = {}
    backend = MagicMock()

    def get(key):
        value, expires = entries.get(key, (None, 0))
        return value if now[0] < expires else None

    def store(key, value, expires):
        entries[key] = (value, now[0] + expires.total_seconds())

    backend.get.side_effect = get
    backend.set.side_effect = store
    backend.delete.side_effect = lambda key: entries.pop(key, None)
    helper = torbox.TorboxHelper()
    helper.client = MagicMock()
    helper.client.token = "account-A-private-token"
    helper.client.get_available_torrent.side_effect = lambda _hash: copy.deepcopy(READY)
    helper.client.create_download_link.return_value = {"data": "https://example.invalid/video"}
    helper.client.add_magnet_link.return_value = {"success": True, "data": {"torrent_id": 7}}
    with patch.object(torbox, "cache", backend, create=True), patch.object(
        torbox, "is_cache_enabled", return_value=True, create=True
    ), patch.object(torbox, "get_public_ip", return_value="192.0.2.1"), patch.object(
        torbox, "DialogProgress"
    ) as dialog, patch.object(torbox, "Monitor") as monitor:
        dialog.return_value.iscanceled.return_value = False
        monitor.return_value.abortRequested.return_value = False
        monitor.return_value.waitForAbort.return_value = False
        yield helper, backend, entries, now


def test_repeated_episodes_reuse_metadata_without_repeating_cloud_lookup(metadata_cache):
    helper, backend, entries, _now = metadata_cache
    for episode in (1, 2):
        result = helper.get_link("testhash", {"tv_data": {"season": 1, "episode": episode}})
        assert result["url"] == "https://example.invalid/video"

    helper.client.get_available_torrent.assert_called_once_with("testhash")
    helper.client.add_magnet_link.assert_not_called()
    assert helper.client.create_download_link.call_args_list == [
        call(7, 1, "192.0.2.1"),
        call(7, 2, "192.0.2.1"),
    ]
    assert len(entries) == 1
    assert backend.set.call_args.args[2] == timedelta(minutes=60)


def test_metadata_expires_after_sixty_minutes(metadata_cache):
    helper, _backend, _entries, now = metadata_cache
    helper.get_link("testhash", {})
    now[0] = 3599
    helper.get_link("testhash", {})
    assert helper.client.get_available_torrent.call_count == 1
    now[0] = 3600
    helper.get_link("testhash", {})
    assert helper.client.get_available_torrent.call_count == 2


def test_metadata_cache_is_account_scoped_without_storing_raw_token_in_key(metadata_cache):
    helper, _backend, entries, _now = metadata_cache
    helper.get_link("testhash", {})
    helper.client.token = "account-B-private-token"
    helper.get_link("testhash", {})
    helper.client.token = "account-A-private-token"
    helper.get_link("testhash", {})
    assert helper.client.get_available_torrent.call_count == 2
    assert len(entries) == 2
    assert all("private-token" not in key and "account-A" not in key for key in entries)


def test_metadata_cache_returns_independent_copies(metadata_cache):
    helper, _backend, _entries, _now = metadata_cache
    first = helper._get_torrent_metadata("testhash")
    first["files"][0]["name"] = "changed.mkv"
    second = helper._get_torrent_metadata("testhash")
    assert second == READY
    second["files"].clear()
    assert helper._get_torrent_metadata("testhash") == READY
    helper.client.get_available_torrent.assert_called_once()


@pytest.mark.parametrize("missing", ["download_finished", "download_present", "id", "files"])
def test_incomplete_or_unavailable_metadata_is_not_cached(metadata_cache, missing):
    helper, backend, entries, _now = metadata_cache
    pending = copy.deepcopy(READY)
    pending.pop(missing)
    helper.client.get_available_torrent.side_effect = None
    helper.client.get_available_torrent.return_value = pending
    helper._get_torrent_metadata("testhash")
    assert entries == {}
    backend.set.assert_not_called()


@pytest.mark.parametrize("recovers", [True, False])
def test_failed_cached_link_gets_one_fresh_resolution_and_no_retry_loop(metadata_cache, recovers):
    helper, _backend, entries, _now = metadata_cache
    helper.get_link("testhash", {})
    fresh = copy.deepcopy(READY)
    fresh["id"] = 9
    helper.client.get_available_torrent.side_effect = lambda _hash: fresh
    helper.client.create_download_link.side_effect = [
        None,
        {"data": "https://fresh/video"} if recovers else None,
    ]
    helper.client.create_download_link.reset_mock()
    data = {"tv_data": {"season": 1, "episode": 2}}

    result = helper.get_link("testhash", data)

    if recovers:
        assert result is data
        assert result["url"] == "https://fresh/video"
    else:
        assert result is None
        assert "url" not in data
        assert entries == {}
    assert helper.client.get_available_torrent.call_count == 2
    assert helper.client.create_download_link.call_args_list == [
        call(7, 2, "192.0.2.1"),
        call(9, 2, "192.0.2.1"),
    ]
    helper.client.add_magnet_link.assert_not_called()


def test_stale_cache_refresh_keeps_bounded_wait_and_submits_magnet_once(metadata_cache):
    helper, _backend, entries, _now = metadata_cache
    helper.get_link("testhash", {})
    helper.client.get_available_torrent.reset_mock()
    helper.client.get_available_torrent.side_effect = None
    helper.client.get_available_torrent.return_value = None
    helper.client.add_magnet_link.return_value = {"success": True, "detail": "Found Cached"}
    helper.client.create_download_link.return_value = None
    helper.client.create_download_link.reset_mock()
    data = {"title": "Show"}

    assert helper.get_link("testhash", data) is None

    assert data == {"title": "Show"}
    assert entries == {}
    assert helper.client.get_available_torrent.call_count == 5
    helper.client.add_magnet_link.assert_called_once()
    helper.client.create_download_link.assert_called_once()


@pytest.mark.parametrize("token", [None, ""])
def test_missing_account_identity_never_reuses_metadata(metadata_cache, token):
    helper, backend, entries, _now = metadata_cache
    helper.client.token = token
    helper.get_link("testhash", {})
    helper.get_link("testhash", {})
    assert helper.client.get_available_torrent.call_count == 2
    assert entries == {}
    backend.get.assert_not_called()
    backend.set.assert_not_called()


def test_malformed_cached_files_are_refetched(metadata_cache):
    helper, _backend, entries, _now = metadata_cache
    helper.get_link("testhash", {})
    next(iter(entries.values()))[0]["files"][0].pop("id")
    assert helper.get_link("testhash", {})["url"] == "https://example.invalid/video"
    assert helper.client.get_available_torrent.call_count == 2


def test_warm_cache_is_visible_in_safe_timing_logs(metadata_cache):
    helper, _backend, _entries, _now = metadata_cache
    helper.get_link("testhash", {})
    with patch("xbmc.log") as logger:
        helper.get_link("testhash", {})
    lines = [item.args[0] for item in logger.call_args_list if "[PLAYBACK-TIMING]" in item.args[0]]
    assert any("stage=torbox_metadata_cache" in line and "outcome=hit" in line for line in lines)
    assert not any("private-token" in line for line in lines)


def test_disabled_cache_keeps_existing_lookup_behavior(metadata_cache):
    helper, backend, entries, _now = metadata_cache
    with patch.object(torbox, "is_cache_enabled", return_value=False):
        helper.get_link("testhash", {})
        helper.get_link("testhash", {})
    assert helper.client.get_available_torrent.call_count == 2
    assert entries == {}
    backend.set.assert_not_called()


@pytest.mark.parametrize("failure", ["get", "set"])
def test_cache_backend_failure_does_not_break_playback(metadata_cache, failure):
    helper, backend, _entries, _now = metadata_cache
    getattr(backend, failure).side_effect = OSError("cache unavailable")
    assert helper.get_link("testhash", {})["url"] == "https://example.invalid/video"


def test_explicit_cloud_ids_do_not_use_metadata_cache(metadata_cache):
    helper, backend, _entries, _now = metadata_cache
    assert helper.get_link("testhash", {"torrent_id": 10, "file_id": 1})["url"]
    backend.get.assert_not_called()
    backend.set.assert_not_called()
    helper.client.get_available_torrent.assert_not_called()


def test_stale_link_refresh_survives_cache_delete_failure(metadata_cache):
    helper, backend, _entries, _now = metadata_cache
    helper.get_link("testhash", {})
    backend.delete.side_effect = OSError("cache unavailable")
    helper.client.create_download_link.side_effect = [None, {"data": "https://fresh/video"}]
    helper.client.create_download_link.reset_mock()

    assert helper.get_link("testhash", {})["url"] == "https://fresh/video"

    assert helper.client.get_available_torrent.call_count == 2
    assert helper.client.create_download_link.call_count == 2
