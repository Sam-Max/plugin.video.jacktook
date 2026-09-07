import base64
import re
from unittest.mock import MagicMock

import pytest
import requests

from lib.api.nuvio import NuvioClient, is_nuvio_progress_sync_enabled


def _response(status_code, payload=None):
    response = MagicMock(status_code=status_code)
    response.json.return_value = payload
    return response


def _device_start_response():
    return _response(
        200,
        [
            {
                "device_code": "device-code-secret",
                "user_code": "USER-CODE",
                "verification_uri": "https://nuvio.tv/activate",
                "verification_uri_complete": "https://nuvio.tv/activate?code=private",
                "expires_at": "not-a-date",
                "poll_interval_seconds": 1,
            }
        ],
    )


def _device_login_mocks(monkeypatch, responses, cancelled=False, selected=0):
    post = MagicMock(side_effect=responses)
    dialog = MagicMock()
    dialog.select.return_value = selected
    progress_dialog = MagicMock()
    progress_dialog.iscanceled = cancelled
    monitor = MagicMock()
    monitor.abortRequested.return_value = False
    monitor.waitForAbort.return_value = False
    monkeypatch.setattr("lib.api.nuvio.requests.post", post)
    monkeypatch.setattr("lib.api.nuvio.xbmcgui.Dialog", MagicMock(return_value=dialog))
    monkeypatch.setattr("lib.api.nuvio.QRProgressDialog", MagicMock(return_value=progress_dialog))
    monkeypatch.setattr("lib.api.nuvio.xbmc.Monitor", MagicMock(return_value=monitor))
    monkeypatch.setattr("lib.api.nuvio.make_qrcode", MagicMock(return_value="qr.png"))
    monkeypatch.setattr("lib.api.nuvio.notification", MagicMock())
    monkeypatch.setattr("lib.api.nuvio.set_setting", MagicMock())
    monkeypatch.setattr("lib.api.nuvio.translation", lambda string_id: f"text-{string_id}")
    monkeypatch.setattr(NuvioClient, "_wait_for_device_poll", staticmethod(lambda *_args: True))
    return post, dialog, progress_dialog, monitor


def test_device_nonce_is_base64url_without_padding(monkeypatch):
    monkeypatch.setattr("lib.api.nuvio.secrets.token_bytes", lambda length: b"\xff" * length)

    nonce = NuvioClient._device_nonce()

    assert re.fullmatch(r"[A-Za-z0-9_-]{32}", nonce)
    assert "=" not in nonce
    assert base64.urlsafe_b64decode(nonce + "==") == b"\xff" * 24


def test_authenticate_runs_qr_pending_approved_exchange_and_profile_selection(monkeypatch):
    post, dialog, progress_dialog, _monitor = _device_login_mocks(
        monkeypatch,
        [
            _device_start_response(),
            _response(200, [{"status": "pending", "poll_interval_seconds": 1}]),
            _response(200, [{"status": "approved", "poll_interval_seconds": 4}]),
            _response(
                200,
                {
                    "access_token": "access-secret",
                    "refresh_token": "refresh-secret",
                    "expires_in": 3600,
                },
            ),
            _response(200, [{"profile_index": 2, "name": "Main"}]),
        ],
    )

    assert NuvioClient().authenticate() is True

    nonce = post.call_args_list[0].kwargs["json"]["p_device_nonce"]
    assert re.fullmatch(r"[A-Za-z0-9_-]{32}", nonce)
    assert all(
        call.kwargs["headers"] == NuvioClient()._device_login_headers
        for call in post.call_args_list[:4]
    )
    assert post.call_args_list[0].args[0].endswith("/rest/v1/rpc/start_device_login_session")
    assert post.call_args_list[0].kwargs["json"] == {
        "p_device_nonce": nonce,
        "p_redirect_base_url": "https://nuvio.tv/link",
        "p_device_type": "tv",
    }
    assert post.call_args_list[1].kwargs["json"] == {
        "p_code": "device-code-secret",
        "p_device_nonce": nonce,
    }
    assert post.call_args_list[2].kwargs["json"] == {
        "p_code": "device-code-secret",
        "p_device_nonce": nonce,
    }
    assert post.call_args_list[3].args[0].endswith("/functions/v1/tv-logins-exchange")
    assert post.call_args_list[3].kwargs["json"] == {
        "code": "device-code-secret",
        "device_nonce": nonce,
    }
    assert post.call_args_list[4].args[0].endswith("/rest/v1/rpc/sync_pull_profiles")
    assert post.call_args_list[4].kwargs["headers"]["Authorization"] == "Bearer access-secret"
    assert post.call_args_list[1].kwargs["json"]["p_device_nonce"] == nonce
    assert post.call_args_list[3].kwargs["json"]["device_nonce"] == nonce
    assert progress_dialog.setup.call_args.args[2:4] == ("https://nuvio.tv/activate", "USER-CODE")
    assert dialog.input.call_count == 0
    dialog.select.assert_called_once_with("text-91017", ["2: Main"])


def test_qr_uses_only_complete_verification_uri_and_displays_manual_values(monkeypatch):
    _post, _dialog, progress_dialog, _monitor = _device_login_mocks(
        monkeypatch,
        [_device_start_response()],
        cancelled=True,
    )
    make_qrcode = __import__("lib.api.nuvio", fromlist=["make_qrcode"]).make_qrcode

    assert NuvioClient().authenticate() is False

    make_qrcode.assert_called_once_with("https://nuvio.tv/activate?code=private")
    assert progress_dialog.setup.call_args.args[2:4] == ("https://nuvio.tv/activate", "USER-CODE")


def test_authenticate_uses_profile_one_for_a_verified_empty_profile_list(monkeypatch):
    _post, dialog, _progress_dialog, _monitor = _device_login_mocks(
        monkeypatch,
        [
            _device_start_response(),
            _response(200, [{"status": "approved"}]),
            _response(200, {"access_token": "access", "refresh_token": "refresh"}),
            _response(200, []),
        ],
    )
    settings = __import__("lib.api.nuvio", fromlist=["set_setting"]).set_setting

    assert NuvioClient().authenticate() is True

    assert ("nuvio_profile_id", "1") in [call.args for call in settings.call_args_list]
    dialog.select.assert_not_called()


def test_cancellation_stops_before_polling(monkeypatch):
    post, _dialog, progress_dialog, _monitor = _device_login_mocks(
        monkeypatch,
        [_device_start_response()],
        cancelled=True,
    )
    log = MagicMock()
    monkeypatch.setattr("lib.api.nuvio.kodilog", log)

    assert NuvioClient().authenticate() is False

    assert post.call_count == 1
    progress_dialog.close_dialog.assert_called_once_with()
    assert "cancelled" in str(log.call_args_list)


@pytest.mark.parametrize("status", ("expired", "used", "cancelled"))
def test_terminal_device_login_states_stop_without_exchange(monkeypatch, status):
    post, _dialog, _progress_dialog, _monitor = _device_login_mocks(
        monkeypatch,
        [_device_start_response(), _response(200, [{"status": status}])],
    )

    assert NuvioClient().authenticate() is False

    assert post.call_count == 2
    assert not any("tv-logins-exchange" in call.args[0] for call in post.call_args_list)


def test_start_validation_and_poll_validation_are_actionable(monkeypatch):
    _post, _dialog, _progress_dialog, _monitor = _device_login_mocks(
        monkeypatch,
        [_response(200, [])],
    )
    notification = __import__("lib.api.nuvio", fromlist=["notification"]).notification

    assert NuvioClient().authenticate() is False
    notification.assert_called_once_with("text-91012", time=5000)

    _post, _dialog, _progress_dialog, _monitor = _device_login_mocks(
        monkeypatch,
        [_device_start_response(), _response(200, {"status": "pending"})],
    )
    notification = __import__("lib.api.nuvio", fromlist=["notification"]).notification

    assert NuvioClient().authenticate() is False
    notification.assert_called_once_with("text-91013", time=5000)


def test_legacy_start_fallback_requires_the_missing_function_condition(monkeypatch):
    missing_function = _response(
        404,
        {
            "message": "Could not find the function public.start_device_login_session in the schema cache"
        },
    )
    post, _dialog, _progress_dialog, _monitor = _device_login_mocks(
        monkeypatch,
        [
            missing_function,
            _response(
                200,
                [
                    {
                        "code": "legacy-device-code",
                        "web_url": "https://nuvio.tv/legacy?code=private",
                        "expires_at": "not-a-date",
                        "poll_interval_seconds": 3,
                    }
                ],
            ),
            _response(200, [{"status": "approved"}]),
            _response(200, {"access_token": "access", "refresh_token": "refresh"}),
            _response(200, []),
        ],
    )

    assert NuvioClient().authenticate() is True

    nonce = post.call_args_list[0].kwargs["json"]["p_device_nonce"]
    assert post.call_args_list[1].args[0].endswith("/rest/v1/rpc/start_tv_login_session")
    assert post.call_args_list[1].kwargs["json"] == {
        "p_device_nonce": nonce,
        "p_redirect_base_url": "https://nuvio.tv",
    }


def test_start_does_not_use_legacy_fallback_for_other_failures(monkeypatch):
    post, _dialog, _progress_dialog, _monitor = _device_login_mocks(
        monkeypatch,
        [_response(404, {"message": "Could not find the function public.some_other_function"})],
    )

    assert NuvioClient().authenticate() is False

    assert post.call_count == 1


def test_exchange_failure_is_actionable(monkeypatch):
    _post, _dialog, _progress_dialog, _monitor = _device_login_mocks(
        monkeypatch,
        [
            _device_start_response(),
            _response(200, [{"status": "approved"}]),
            _response(200, {"access_token": "access-without-refresh"}),
        ],
    )
    notification = __import__("lib.api.nuvio", fromlist=["notification"]).notification

    assert NuvioClient().authenticate() is False

    notification.assert_called_once_with("text-91014", time=5000)


def test_parsed_expiry_creates_a_monotonic_deadline(monkeypatch):
    monkeypatch.setattr("lib.api.nuvio.time.time", lambda: 1000)
    monkeypatch.setattr("lib.api.nuvio.time.monotonic", lambda: 100)

    assert NuvioClient._device_login_deadline("1970-01-01T00:17:40Z") == 160
    assert NuvioClient._device_login_deadline("not-a-date") is None
    assert NuvioClient._device_poll_interval(0) is None
    assert NuvioClient._device_poll_interval(1) == 2


def test_device_login_logs_redact_nonce_codes_urls_and_tokens(monkeypatch):
    log = MagicMock()
    secret_values = ("nonce-secret", "device-code-secret", "USER-CODE", "private", "access-secret")
    _device_login_mocks(monkeypatch, [requests.Timeout("nonce-secret")])
    monkeypatch.setattr("lib.api.nuvio.kodilog", log)
    monkeypatch.setattr(NuvioClient, "_device_nonce", staticmethod(lambda: "nonce-secret"))

    assert NuvioClient().authenticate() is False

    logged = " ".join(str(call) for call in log.call_args_list)
    assert all(secret not in logged for secret in secret_values)


def test_push_watch_progress_uses_documented_movie_contract(monkeypatch):
    post = MagicMock(return_value=_response(204))
    monkeypatch.setattr("lib.api.nuvio.requests.post", post)
    client = NuvioClient(
        access_token="access", refresh_token="refresh", expires_at="", profile_id=2
    )

    assert client.push_watch_progress(
        {
            "mode": "movies",
            "ids": {"tmdb_id": "550"},
            "current_time": 3600.25,
            "total_time": 7920,
        }
    )

    assert post.call_args.kwargs["json"]["p_profile_id"] == 2
    assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer access"


def test_progress_payload_uses_canonical_series_episode_identifiers():
    assert NuvioClient.progress_payload(
        {
            "mode": "tv",
            "ids": {"tmdb_id": 1396},
            "tv_data": {"season": "1", "episode": "1"},
            "current_time": 1800,
            "total_time": 3480,
        },
        now_ms=1711600000000,
    ) == {
        "content_id": "tmdb:1396",
        "content_type": "series",
        "video_id": "tmdb:1396:1:1",
        "season": 1,
        "episode": 1,
        "position": 1800000,
        "duration": 3480000,
        "last_watched": 1711600000000,
    }


def test_logout_calls_remote_endpoint_and_clears_all_session_settings(monkeypatch):
    post = MagicMock(return_value=_response(204))
    settings = MagicMock()
    monkeypatch.setattr("lib.api.nuvio.requests.post", post)
    monkeypatch.setattr("lib.api.nuvio.set_setting", settings)

    NuvioClient(
        access_token="access", refresh_token="refresh", expires_at=5000, profile_id=3
    ).logout()

    post.assert_called_once_with(
        "https://api.nuvio.tv/auth/v1/logout",
        headers={"Authorization": "Bearer access", "apikey": NuvioClient.PUBLISHABLE_KEY},
        timeout=5,
    )
    assert ("nuvio_authenticated", "false") in [call.args for call in settings.call_args_list]


def test_sync_requires_enabled_authenticated_session_and_profile(monkeypatch):
    values = {
        "nuvio_enabled": "true",
        "nuvio_authenticated": "true",
        "nuvio_access_token": "access",
        "nuvio_profile_id": "6",
    }
    monkeypatch.setattr("lib.api.nuvio.get_setting", values.get)

    assert is_nuvio_progress_sync_enabled() is True
    values["nuvio_profile_id"] = "7"
    assert is_nuvio_progress_sync_enabled() is False
