from unittest.mock import MagicMock, patch

import pytest

from lib.api.debrid.base import ProviderException
from lib.clients.debrid import torbox

READY = {
    "id": 7,
    "download_finished": True,
    "download_present": True,
    "files": [{"id": 2, "name": "Show.S01E02.mkv", "size": 100}],
}


@pytest.fixture
def waiting():
    helper = torbox.TorboxHelper()
    helper.client = MagicMock()
    helper.client.add_magnet_link.return_value = {"success": True, "detail": "Found Cached"}
    helper.client.create_download_link.return_value = {"data": "https://example.invalid/video"}
    with patch.object(torbox, "DialogProgress", create=True) as progress, patch.object(
        torbox, "Monitor", create=True
    ) as monitor_class, patch.object(torbox, "get_cached", return_value=None), patch.object(
        torbox, "set_cached"
    ) as store, patch.object(torbox, "notification") as notify, patch.object(
        torbox, "info_hash_to_magnet", return_value="magnet:testhash"
    ), patch.object(torbox, "get_public_ip", return_value="192.0.2.1"), patch("time.sleep"):
        dialog = progress.return_value
        dialog.iscanceled.return_value = False
        monitor = monitor_class.return_value
        monitor.abortRequested.return_value = False
        monitor.waitForAbort.return_value = False
        yield helper, dialog, monitor, store, notify


@pytest.mark.parametrize("stale", [None, {"id": 7, "files": []}])
def test_cached_add_waits_until_playback_metadata_is_visible_without_resubmitting(waiting, stale):
    helper, dialog, monitor, store, _notify = waiting
    helper.client.get_available_torrent.side_effect = [None, None, stale, READY]
    data = {"tv_data": {"season": 1, "episode": 2}}

    result = helper.get_link("testhash", data)

    assert result is data
    assert result["url"] == "https://example.invalid/video"
    helper.client.add_magnet_link.assert_called_once_with("magnet:testhash")
    assert helper.client.get_available_torrent.call_count == 4
    assert monitor.waitForAbort.call_count == 2
    helper.client.create_download_link.assert_called_once_with(7, 2, "192.0.2.1")
    dialog.close.assert_called_once()
    store.assert_not_called()


@pytest.mark.parametrize("cached", [True, False])
def test_pack_waits_for_real_metadata_instead_of_using_the_add_envelope(waiting, cached):
    helper, dialog, _monitor, store, _notify = waiting
    if cached:
        helper.client.get_available_torrent.side_effect = [None, None, None, READY]
    else:
        helper.client.add_magnet_link.return_value = {
            "success": True,
            "data": {"torrent_id": 7},
        }
        helper.client.get_available_torrent.side_effect = [None, None, READY]

    result = helper.get_pack_info("testhash")

    assert result == {"id": 7, "torrent_id": 7, "files": [(2, "Show.S01E02.mkv")]}
    store.assert_called_once_with(result, "testhash")
    helper.client.add_magnet_link.assert_called_once_with("magnet:testhash")
    helper.client.create_download_link.assert_not_called()
    dialog.close.assert_called_once()


@pytest.mark.parametrize("pack", [False, True])
def test_invisible_torrent_stops_after_three_polls_without_creating_link_or_caching(waiting, pack):
    helper, dialog, monitor, store, notify = waiting
    helper.client.get_available_torrent.return_value = None
    data = {"title": "Show"}

    result = helper.get_pack_info("testhash") if pack else helper.get_link("testhash", data)

    assert result is None
    assert data == {"title": "Show"}
    assert helper.client.get_available_torrent.call_count == 5  # Two add lookups, three polls.
    assert monitor.waitForAbort.call_count == 3
    helper.client.add_magnet_link.assert_called_once()
    helper.client.create_download_link.assert_not_called()
    store.assert_not_called()
    notify.assert_called_once_with(
        "Torbox is still processing this torrent. Please try again in a moment."
    )
    dialog.close.assert_called_once()


@pytest.mark.parametrize("cancel", ["before_wait", "after_wait", "shutdown"])
def test_cancel_or_shutdown_stops_waiting_without_another_lookup(waiting, cancel):
    helper, dialog, monitor, store, notify = waiting
    helper.client.get_available_torrent.return_value = None
    if cancel == "before_wait":
        dialog.iscanceled.return_value = True
    elif cancel == "after_wait":
        dialog.iscanceled.side_effect = [False, True]
    else:
        monitor.waitForAbort.return_value = True
    data = {"title": "Show"}

    assert helper.get_link("testhash", data) is None

    assert data == {"title": "Show"}
    assert helper.client.get_available_torrent.call_count == 2
    helper.client.add_magnet_link.assert_called_once()
    helper.client.create_download_link.assert_not_called()
    store.assert_not_called()
    notify.assert_not_called()
    dialog.close.assert_called_once()


def test_cancel_during_lookup_does_not_start_playback(waiting):
    helper, dialog, _monitor, _store, notify = waiting
    calls = []

    def lookup(_info_hash):
        calls.append(True)
        if len(calls) == 3:
            dialog.iscanceled.return_value = True
            return READY
        return None

    helper.client.get_available_torrent.side_effect = lookup
    data = {"title": "Show"}
    assert helper.get_link("testhash", data) is None
    assert data == {"title": "Show"}
    helper.client.create_download_link.assert_not_called()
    notify.assert_not_called()
    dialog.close.assert_called_once()


def test_missing_torrent_id_never_creates_an_invalid_download_link(waiting):
    helper, dialog, monitor, _store, _notify = waiting
    helper.client.get_available_torrent.return_value = {"files": READY["files"]}

    assert helper.get_link("testhash", {}) is None

    assert monitor.waitForAbort.call_count == 3
    helper.client.create_download_link.assert_not_called()
    dialog.close.assert_called_once()


def test_lookup_error_closes_dialog_without_resubmitting_or_retrying_the_error(waiting):
    helper, dialog, _monitor, store, _notify = waiting
    helper.client.get_available_torrent.side_effect = [None, None, ProviderException("API failed")]
    with pytest.raises(ProviderException, match="API failed"):
        helper.get_link("testhash", {})
    assert helper.client.get_available_torrent.call_count == 3
    helper.client.add_magnet_link.assert_called_once()
    helper.client.create_download_link.assert_not_called()
    store.assert_not_called()
    dialog.close.assert_called_once()


def test_ready_metadata_keeps_immediate_playback_without_opening_a_wait_dialog(waiting):
    helper, dialog, monitor, _store, _notify = waiting
    helper.client.get_available_torrent.return_value = READY

    result = helper.get_link("testhash", {})

    assert result["url"] == "https://example.invalid/video"
    helper.client.add_magnet_link.assert_not_called()
    helper.client.create_download_link.assert_called_once_with(7, 2, "192.0.2.1")
    dialog.create.assert_not_called()
    monitor.waitForAbort.assert_not_called()
