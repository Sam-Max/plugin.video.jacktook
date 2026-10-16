import json
from unittest.mock import patch

import pytest
import requests

from lib.api.debrid.base import ProviderException
from lib.api.debrid.torbox import Torbox
from lib.clients.debrid.torbox import TorboxHelper
from lib.db.cached import cache
from lib.nav import debrid as debrid_navigation


def response(payload, status=200):
    result = requests.Response()
    result.status_code = status
    result._content = json.dumps(payload).encode("utf-8")
    result.headers["Content-Type"] = "application/json"
    result.url = "https://example.invalid/torbox"
    return result


@pytest.fixture
def api():
    client = Torbox("test-token")
    with patch.object(client.session, "request") as request, patch(
        "lib.api.debrid.base.notification"
    ):
        yield client, request


@pytest.mark.parametrize(
    "payload",
    [
        {"success": False, "error": "COOLDOWN_LIMIT", "detail": "Please wait", "data": None},
        {"success": True, "data": None},
        {"success": True, "data": {}},
        {"success": True, "data": ["not a torrent"]},
        {"success": True, "data": [{"files": "not files"}]},
        {"success": True, "data": [{"files": [None]}]},
        {"data": []},
        [],
    ],
)
def test_invalid_cloud_response_is_not_cached_as_empty_library(api, payload):
    client, request = api
    request.return_value = response(payload)
    helper = TorboxHelper()
    helper.client = client
    with patch.object(debrid_navigation, "TorboxHelper", return_value=helper), patch.object(
        cache, "get", return_value=None
    ), patch.object(cache, "set") as store, patch.object(
        debrid_navigation, "addDirectoryItem"
    ) as add_item, patch.object(debrid_navigation, "endOfDirectory", create=True) as close:
        debrid_navigation.get_tb_downloads({})

    store.assert_not_called()
    add_item.assert_not_called()
    close.assert_called_once_with(
        debrid_navigation.get_addon_handle(), succeeded=False, cacheToDisc=False
    )


def test_valid_empty_cloud_is_cached_and_closed_successfully(api):
    client, request = api
    request.return_value = response({"success": True, "data": []})
    helper = TorboxHelper()
    helper.client = client
    with patch.object(debrid_navigation, "TorboxHelper", return_value=helper), patch.object(
        cache, "get", return_value=None
    ), patch.object(cache, "set") as store, patch.object(
        debrid_navigation, "end_of_directory"
    ) as close, patch.object(debrid_navigation, "apply_section_view"):
        debrid_navigation.get_tb_downloads({})

    assert store.call_args.args[1] == []
    close.assert_called_once_with()


def test_valid_cloud_list_preserves_metadata_and_request_options(api):
    client, request = api
    payload = {
        "success": True,
        "data": [{"id": 7, "hash": "testhash", "files": [{"id": 2, "name": "show.mkv"}]}],
    }
    request.return_value = response(payload)
    assert client.get_user_torrent_list() == payload
    assert request.call_args.kwargs["method"] == "GET"
    assert request.call_args.kwargs["params"] == {"bypass_cache": "true"}


@pytest.mark.parametrize(
    "payload",
    [
        {"success": False, "error": "DATABASE_ERROR", "data": []},
        {"success": True, "data": None},
        {"success": True, "data": {}},
        {"success": True, "data": [None]},
        {"success": True, "data": [{"hash": 42}]},
    ],
)
def test_cache_check_rejects_failures_and_invalid_payloads(api, payload):
    client, request = api
    request.return_value = response(payload)
    with pytest.raises(ProviderException):
        client.get_torrent_instant_availability(["testhash"])


@pytest.mark.parametrize("data", [[], ["testhash"], [{"hash": "testhash"}]])
def test_cache_check_preserves_supported_list_shapes(api, data):
    client, request = api
    payload = {"success": True, "data": data}
    request.return_value = response(payload)
    assert client.get_torrent_instant_availability(["testhash"]) == payload


@pytest.mark.parametrize("upload", [False, True])
def test_successful_add_invalidates_listing_and_next_visit_refetches(api, upload):
    client, request = api
    added = {"success": True, "data": {"torrent_id": 7, "hash": "newhash"}}
    request.return_value = response(added)
    key = "cloud_downloads|Torbox|1|files-v2"
    stored = {key: [{"name": "old.mkv"}]}
    helper = TorboxHelper()
    helper.client = client
    with patch.object(cache, "delete", side_effect=lambda key: stored.pop(key, None)) as delete:
        if upload:
            result = client.add_torrent_file(b"torrent-data", "show.torrent")
            assert request.call_args.kwargs["files"]["file"][1] == b"torrent-data"
        else:
            result = client.add_magnet_link("magnet:test")
            assert request.call_args.kwargs["data"]["magnet"] == "magnet:test"
    assert result == added
    delete.assert_called_once_with(key)
    assert stored == {}

    request.return_value = response({"success": True, "data": []})
    request.reset_mock()
    with patch.object(debrid_navigation, "TorboxHelper", return_value=helper), patch.object(
        cache, "get", side_effect=stored.get
    ), patch.object(cache, "set") as store, patch.object(
        debrid_navigation, "end_of_directory"
    ), patch.object(debrid_navigation, "apply_section_view"):
        debrid_navigation.get_tb_downloads({})
    request.assert_called_once()
    assert request.call_args.kwargs["url"].endswith("/torrents/mylist")
    assert store.call_args.args[:2] == (key, [])


@pytest.mark.parametrize("upload", [False, True])
@pytest.mark.parametrize(
    "payload",
    [
        {"success": False, "detail": "Rejected", "data": {}},
        {"success": True, "data": None},
        {"success": True, "data": []},
        [],
    ],
)
def test_rejected_or_malformed_add_preserves_cached_listing(api, upload, payload):
    client, request = api
    request.return_value = response(payload)
    with patch.object(cache, "delete") as delete, pytest.raises(ProviderException):
        if upload:
            client.add_torrent_file(b"torrent-data")
        else:
            client.add_magnet_link("magnet:test")
    delete.assert_not_called()


def test_duplicate_queued_magnet_still_recovers_and_invalidates_listing(api):
    client, request = api
    request.return_value = response(
        {"success": False, "error": "DIFF_ISSUE", "detail": "Download already queued"}, 400
    )
    with patch.object(cache, "delete") as delete:
        result = client.add_magnet_link("magnet:test")
    assert result["success"] is True
    assert result["queued"] is True
    delete.assert_called_once_with("cloud_downloads|Torbox|1|files-v2")


def test_auth_poll_and_download_link_keep_expected_failure_behavior(api):
    client, request = api
    payload = {"success": False, "error": "INVALID_DEVICE", "detail": "Not ready"}
    request.return_value = response(payload, 400)
    with patch.object(cache, "delete") as delete, patch(
        "lib.api.debrid.torbox.notification"
    ) as notify:
        assert client.authorize("device-code") == payload
        assert client.create_download_link(7, 2) is None
    notify.assert_called_once_with("Failed to create download link: Not ready")
    delete.assert_not_called()
