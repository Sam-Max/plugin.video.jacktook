from unittest.mock import MagicMock, patch

import requests

from lib.api.debrid.offcloud import Offcloud
from lib.clients.debrid.offcloud import OffcloudHelper
from lib.domain.torrent import TorrentStream
from lib.services.debrid.auth import run_offcloud_auth
from lib.utils.general.utils import DebridType, IndexerType


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.headers = {"Content-Type": "application/json"}
        self.text = ""
        self.url = "https://offcloud.com/api/test"

    @property
    def ok(self):
        return 200 <= self.status_code < 400

    def json(self):
        return self._payload

    def raise_for_status(self):
        if not self.ok:
            error = requests.RequestException("HTTP error")
            error.response = self
            raise error


def test_offcloud_client_uses_bearer_auth_and_cache_info_payload():
    session = MagicMock()
    session.request.return_value = FakeResponse([{"cached": True}])
    client = Offcloud("token-123", session=session)

    result = client.get_cache_info(["magnet:?xt=urn:btih:abc"], include_files=True)

    assert result == [{"cached": True}]
    session.request.assert_called_once_with(
        method="POST",
        url="https://offcloud.com/api/cache/info",
        params={},
        data=None,
        json={"urls": ["magnet:?xt=urn:btih:abc"], "includeFiles": True},
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": "Bearer token-123",
        },
        timeout=15,
    )


def test_offcloud_client_flattens_nested_cloud_status():
    session = MagicMock()
    session.request.return_value = FakeResponse(
        {"status": {"status": "downloaded", "requestId": "req-1"}}
    )
    client = Offcloud("token-123", session=session)

    assert client.get_cloud_status("req-1") == {"status": "downloaded", "requestId": "req-1"}


def test_offcloud_client_requests_oauth_device_code_without_query_token():
    session = MagicMock()
    session.request.return_value = FakeResponse(
        {
            "device_code": "device-1",
            "user_code": "ABCD-EFGH",
            "verification_uri": "https://offcloud.com/activate",
            "interval": 5,
            "expires_in": 600,
        }
    )
    client = Offcloud("", session=session)

    result = client.get_device_code()

    assert result["device_code"] == "device-1"
    session.request.assert_called_once_with(
        method="POST",
        url="https://offcloud.com/oauth/device/code",
        params={},
        data=None,
        json={},
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        timeout=15,
    )


def test_offcloud_client_requests_oauth_without_existing_bearer_auth():
    session = MagicMock()
    session.request.return_value = FakeResponse(
        {
            "device_code": "device-1",
            "user_code": "ABCD-EFGH",
            "verification_uri": "https://offcloud.com/activate",
            "interval": 5,
            "expires_in": 600,
        }
    )
    client = Offcloud("old-token", session=session)

    result = client.get_device_code()

    assert result["device_code"] == "device-1"
    session.request.assert_called_once_with(
        method="POST",
        url="https://offcloud.com/oauth/device/code",
        params={},
        data=None,
        json={},
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        timeout=15,
    )
    assert client.headers["Authorization"] == "Bearer old-token"


def test_offcloud_client_authorize_returns_expected_oauth_error_payload():
    session = MagicMock()
    session.request.return_value = FakeResponse({"error": "authorization_pending"}, status_code=400)
    client = Offcloud("", session=session)

    result = client.authorize("device-1")

    assert result == {"error": "authorization_pending"}
    session.request.assert_called_once_with(
        method="POST",
        url="https://offcloud.com/oauth/token",
        params={},
        data=None,
        json={
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": "device-1",
        },
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        timeout=15,
    )


def test_offcloud_helper_check_cached_preserves_response_order_mapping():
    helper = OffcloudHelper()
    helper.client = MagicMock()
    helper.client.get_cache_info.return_value = [{"cached": False}, {"cached": True}]
    results = [TorrentStream(infoHash="hash1"), TorrentStream(infoHash="hash2")]
    cached_results = []
    uncached_results = []
    lock = MagicMock()
    lock.__enter__.return_value = None
    lock.__exit__.return_value = None

    with patch("lib.clients.debrid.offcloud.debrid_dialog_update"):
        helper.check_cached(results, cached_results, uncached_results, 2, MagicMock(), lock)

    assert [item.infoHash for item in cached_results] == ["hash2"]
    assert [item.infoHash for item in uncached_results] == ["hash1"]
    assert cached_results[0].type == IndexerType.DEBRID
    assert cached_results[0].debridType == DebridType.OC


def test_offcloud_helper_get_link_uses_cache_download_and_filters_tv_episode():
    helper = OffcloudHelper()
    helper.client = MagicMock()
    helper.client.create_cache_download.return_value = [
        {"filename": "show.s01e01.mkv", "size": 10, "url": "https://wrong"},
        {"filename": "show.s01e02.mkv", "size": 20, "url": "https://right"},
    ]

    data = helper.get_link(
        "abc123",
        {"tv_data": {"season": 1, "episode": 2}},
    )

    assert data is not None
    assert data["url"] == "https://right"


def test_offcloud_helper_get_cloud_downloads_uses_detailed_explore_files():
    helper = OffcloudHelper()
    helper.client = MagicMock()
    helper.client.get_cloud_history.return_value = [
        {"requestId": "req-1", "fileName": "Release", "status": "downloaded", "createdOn": "2026"},
        {"requestId": "req-2", "fileName": "Pending", "status": "created"},
    ]
    helper.client.explore_cloud_download.return_value = {
        "files": [
            {"path": "Release/sample.txt", "size": 1, "url": "https://text"},
            {"path": "Release/video.mkv", "size": 100, "url": "https://video"},
        ]
    }

    assert helper.get_cloud_downloads() == [
        {
            "name": "Release/video.mkv",
            "request_id": "req-1",
            "url": "https://video",
            "created_at": "2026",
        }
    ]
    helper.client.explore_cloud_download.assert_called_once_with("req-1", detailed=True)


@patch(
    "lib.services.debrid.auth.translation",
    side_effect=lambda value: "%s" if value == 90604 else str(value),
)
@patch("lib.services.debrid.auth.set_setting")
@patch("lib.services.debrid.auth.copy2clip")
@patch("lib.services.debrid.auth.make_qrcode", return_value="/tmp/qr.png")
@patch("lib.services.debrid.auth.ksleep")
@patch("lib.services.debrid.auth.time", side_effect=[0, 0])
@patch("lib.services.debrid.auth.QRProgressDialog")
@patch("lib.services.debrid.auth.dialog_ok")
def test_run_offcloud_auth_stores_access_token_and_account_email(
    mock_dialog_ok,
    mock_dialog_cls,
    mock_time,
    mock_sleep,
    mock_make_qrcode,
    mock_copy2clip,
    mock_set_setting,
    mock_translation,
):
    client = MagicMock()
    client.get_device_code.return_value = {
        "device_code": "device-1",
        "user_code": "ABCD-EFGH",
        "verification_uri": "https://offcloud.com/activate",
        "verification_uri_complete": "https://offcloud.com/activate?code=ABCD-EFGH",
        "interval": 5,
        "expires_in": 600,
    }
    client.authorize.return_value = {"access_token": "api-key", "token_type": "Bearer"}
    client.get_account_info.return_value = {"email": "tester@example.com"}
    dialog = MagicMock()
    dialog.iscanceled = False
    mock_dialog_cls.return_value = dialog

    run_offcloud_auth(client)

    assert client.token == "api-key"
    client.authorize.assert_called_once_with("device-1")
    client.initialize_headers.assert_called_once_with()
    mock_sleep.assert_called_once_with(5000)
    mock_make_qrcode.assert_called_once_with("https://offcloud.com/activate?code=ABCD-EFGH")
    mock_copy2clip.assert_called_once_with("https://offcloud.com/activate?code=ABCD-EFGH")
    mock_set_setting.assert_any_call("offcloud_token", "api-key")
    mock_set_setting.assert_any_call("offcloud_authorized", "true")
    mock_set_setting.assert_any_call("offcloud_user", "tester@example.com")
    dialog.setup.assert_called_once_with(
        DebridType.OC,
        "/tmp/qr.png",
        "https://offcloud.com/activate",
        "ABCD-EFGH",
        DebridType.OC,
    )
    dialog.update_progress.assert_called_once_with(100, "90545")
    dialog.close_dialog.assert_called_once_with()
    mock_dialog_ok.assert_called_once_with("90544", "90545")


@patch(
    "lib.services.debrid.auth.translation",
    side_effect=lambda value: "%s" if value == 90604 else str(value),
)
@patch("lib.services.debrid.auth.set_setting")
@patch("lib.services.debrid.auth.copy2clip")
@patch("lib.services.debrid.auth.make_qrcode", return_value="/tmp/qr.png")
@patch("lib.services.debrid.auth.ksleep")
@patch("lib.services.debrid.auth.time", side_effect=[0, 0, 1, 2])
@patch("lib.services.debrid.auth.QRProgressDialog")
def test_run_offcloud_auth_slow_down_increases_poll_interval(
    mock_dialog_cls,
    mock_time,
    mock_sleep,
    mock_make_qrcode,
    mock_copy2clip,
    mock_set_setting,
    mock_translation,
):
    client = MagicMock()
    client.get_device_code.return_value = {
        "device_code": "device-1",
        "user_code": "ABCD-EFGH",
        "verification_uri": "https://offcloud.com/activate",
        "interval": 5,
        "expires_in": 600,
    }
    client.authorize.side_effect = [
        {"error": "slow_down"},
        {"access_token": "api-key", "token_type": "Bearer"},
    ]
    client.get_account_info.return_value = {}
    dialog = MagicMock()
    dialog.iscanceled = False
    mock_dialog_cls.return_value = dialog

    run_offcloud_auth(client)

    assert [call.args[0] for call in mock_sleep.call_args_list] == [5000, 10000]
    assert client.token == "api-key"
    assert client.authorize.call_count == 2


@patch(
    "lib.services.debrid.auth.translation",
    side_effect=lambda value: "%s" if value == 90604 else str(value),
)
@patch("lib.services.debrid.auth.set_setting")
@patch("lib.services.debrid.auth.copy2clip")
@patch("lib.services.debrid.auth.make_qrcode", return_value="/tmp/qr.png")
@patch("lib.services.debrid.auth.ksleep")
@patch("lib.services.debrid.auth.time", side_effect=[0, 0, 1, 1])
@patch("lib.services.debrid.auth.QRProgressDialog")
def test_run_offcloud_auth_authorization_pending_keeps_polling(
    mock_dialog_cls,
    mock_time,
    mock_sleep,
    mock_make_qrcode,
    mock_copy2clip,
    mock_set_setting,
    mock_translation,
):
    client = MagicMock()
    client.get_device_code.return_value = {
        "device_code": "device-1",
        "user_code": "ABCD-EFGH",
        "verification_uri": "https://offcloud.com/activate",
        "interval": 5,
        "expires_in": 600,
    }
    client.authorize.side_effect = [
        {"error": "authorization_pending"},
        {"access_token": "api-key", "token_type": "Bearer"},
    ]
    client.get_account_info.return_value = {}
    dialog = MagicMock()
    dialog.iscanceled = False
    mock_dialog_cls.return_value = dialog

    run_offcloud_auth(client)

    assert client.authorize.call_count == 2
    assert [call.args[0] for call in mock_sleep.call_args_list] == [5000, 5000]
    assert client.token == "api-key"
    dialog.update_progress.assert_any_call(0)


@patch(
    "lib.services.debrid.auth.translation",
    side_effect=lambda value: "%s" if value == 90604 else str(value),
)
@patch("lib.services.debrid.auth.set_setting")
@patch("lib.services.debrid.auth.copy2clip")
@patch("lib.services.debrid.auth.make_qrcode", return_value="/tmp/qr.png")
@patch("lib.services.debrid.auth.ksleep")
@patch("lib.services.debrid.auth.time", side_effect=[0, 0])
@patch("lib.services.debrid.auth.QRProgressDialog")
@patch("lib.services.debrid.auth.dialog_ok")
def test_run_offcloud_auth_expired_token_stops_polling(
    mock_dialog_ok,
    mock_dialog_cls,
    mock_time,
    mock_sleep,
    mock_make_qrcode,
    mock_copy2clip,
    mock_set_setting,
    mock_translation,
):
    client = MagicMock()
    client.get_device_code.return_value = {
        "device_code": "device-1",
        "user_code": "ABCD-EFGH",
        "verification_uri": "https://offcloud.com/activate",
        "interval": 5,
        "expires_in": 600,
    }
    client.authorize.return_value = {
        "error": "expired_token",
        "error_description": "The device code has expired",
    }
    dialog = MagicMock()
    dialog.iscanceled = False
    mock_dialog_cls.return_value = dialog

    run_offcloud_auth(client)

    client.authorize.assert_called_once_with("device-1")
    mock_sleep.assert_called_once_with(5000)
    client.initialize_headers.assert_not_called()
    dialog.close_dialog.assert_called_once_with()
    mock_dialog_ok.assert_called_once_with("90548", "The device code has expired")


@patch(
    "lib.services.debrid.auth.translation",
    side_effect=lambda value: "%s" if value == 90604 else str(value),
)
@patch("lib.services.debrid.auth.set_setting")
@patch("lib.services.debrid.auth.copy2clip")
@patch("lib.services.debrid.auth.make_qrcode", return_value="/tmp/qr.png")
@patch("lib.services.debrid.auth.ksleep")
@patch("lib.services.debrid.auth.time", side_effect=[0, 0])
@patch("lib.services.debrid.auth.QRProgressDialog")
@patch("lib.services.debrid.auth.dialog_ok")
def test_run_offcloud_auth_access_denied_stops_polling(
    mock_dialog_ok,
    mock_dialog_cls,
    mock_time,
    mock_sleep,
    mock_make_qrcode,
    mock_copy2clip,
    mock_set_setting,
    mock_translation,
):
    client = MagicMock()
    client.get_device_code.return_value = {
        "device_code": "device-1",
        "user_code": "ABCD-EFGH",
        "verification_uri": "https://offcloud.com/activate",
        "interval": 5,
        "expires_in": 600,
    }
    client.authorize.return_value = {
        "error": "access_denied",
        "error_description": "The user denied authorization",
    }
    dialog = MagicMock()
    dialog.iscanceled = False
    mock_dialog_cls.return_value = dialog

    run_offcloud_auth(client)

    client.authorize.assert_called_once_with("device-1")
    mock_sleep.assert_called_once_with(5000)
    client.initialize_headers.assert_not_called()
    dialog.close_dialog.assert_called_once_with()
    mock_dialog_ok.assert_called_once_with("90548", "The user denied authorization")
