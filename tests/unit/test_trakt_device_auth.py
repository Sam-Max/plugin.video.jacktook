from contextlib import ExitStack
from unittest.mock import Mock, patch

import pytest
import requests

from lib.api.trakt.trakt import TraktAuthentication


def device_code(**overrides):
    result = {
        "device_code": "device-code",
        "user_code": "USER-CODE",
        "verification_url": "https://trakt.tv/activate",
        "expires_in": 10,
        "interval": 1,
    }
    result.update(overrides)
    return result


def response(status_code, payload=None):
    result = Mock(status_code=status_code)
    result.json.return_value = payload
    return result


def run_poll(
    api,
    responses,
    code=None,
    *,
    cancelled=False,
    aborted=False,
    cancel_during_wait=False,
    abort_during_wait=False,
):
    dialog = Mock(iscanceled=cancelled)
    monitor = Mock()
    monitor.abortRequested.return_value = aborted
    clock = [0.0]

    def advance(milliseconds):
        clock[0] += milliseconds / 1000
        if cancel_during_wait:
            dialog.iscanceled = True
        if abort_during_wait:
            monitor.abortRequested.return_value = True

    with ExitStack() as stack:
        stack.enter_context(patch("lib.api.trakt.trakt.trakt_client", return_value="client-id"))
        stack.enter_context(patch("lib.api.trakt.trakt.trakt_secret", return_value="client-secret"))
        stack.enter_context(patch("lib.api.trakt.trakt.make_qrcode", return_value="qr.png"))
        stack.enter_context(patch("lib.api.trakt.trakt.copy2clip"))
        stack.enter_context(patch("lib.api.trakt.trakt.QRProgressDialog", return_value=dialog))
        stack.enter_context(patch("lib.api.trakt.trakt.xbmc.Monitor", return_value=monitor))
        stack.enter_context(
            patch("lib.api.trakt.trakt.time.monotonic", side_effect=lambda: clock[0])
        )
        sleep_mock = stack.enter_context(patch("lib.api.trakt.trakt.sleep", side_effect=advance))
        post_mock = stack.enter_context(
            patch("lib.api.trakt.trakt.requests.post", side_effect=responses)
        )
        failure_mock = stack.enter_context(patch.object(api, "_device_auth_failure"))

        result = api.trakt_get_device_token(code or device_code())

    return result, dialog, failure_mock, post_mock, sleep_mock


@pytest.mark.parametrize(
    "invalid_code",
    [
        None,
        {},
        device_code(device_code=""),
        device_code(user_code=""),
        device_code(verification_url=""),
        device_code(expires_in=0),
        device_code(interval=0),
        device_code(expires_in=float("nan")),
        device_code(interval=float("nan")),
        device_code(expires_in=float("inf")),
        device_code(interval=float("inf")),
    ],
)
def test_device_code_validation_rejects_missing_or_invalid_fields(invalid_code):
    assert TraktAuthentication._validate_device_code(invalid_code) is False


def test_get_device_code_validates_response_before_use():
    api = TraktAuthentication()
    with patch("lib.api.trakt.trakt.trakt_client", return_value="client-id"), patch.object(
        api, "call_trakt", return_value={"device_code": "incomplete"}
    ), patch.object(api, "_device_auth_failure") as failure:
        result = api.trakt_get_device_code()

    assert result is None
    failure.assert_called_once()


def test_get_device_code_transport_failure_is_reported():
    api = TraktAuthentication()
    with patch("lib.api.trakt.trakt.trakt_client", return_value="client-id"), patch.object(
        api, "call_trakt", side_effect=requests.ConnectionError("offline")
    ), patch.object(api, "_device_auth_failure") as failure:
        result = api.trakt_get_device_code()

    assert result is None
    assert "offline" in failure.call_args.args[0]


def test_device_auth_failure_logs_and_notifies():
    api = TraktAuthentication()
    with patch("lib.api.trakt.trakt.kodilog") as log, patch(
        "lib.api.trakt.trakt.notification"
    ) as notify, patch("lib.api.trakt.trakt.translation", return_value="Trakt Error"):
        api._device_auth_failure("Restart authorization.")

    assert api._device_auth_failure_shown is True
    log.assert_called_once_with("Trakt device authorization failed: Restart authorization.")
    notify.assert_called_once_with("Trakt Error: Restart authorization.", time=5000)


def test_pending_then_success_returns_token_and_closes_dialog():
    api = TraktAuthentication()
    token = {"access_token": "access", "refresh_token": "refresh"}
    result, dialog, failure, post, sleep_mock = run_poll(
        api, [response(400), response(200, token)]
    )

    assert result == token
    assert post.call_count == 2
    assert sum(call.args[0] for call in sleep_mock.call_args_list) == 2000
    assert max(call.args[0] for call in sleep_mock.call_args_list) <= 250
    failure.assert_not_called()
    dialog.close_dialog.assert_called_once_with()


def test_device_token_poll_includes_contract_headers():
    api = TraktAuthentication()
    token = {"access_token": "access", "refresh_token": "refresh"}
    with patch("lib.api.trakt.trakt.ADDON_NAME", "Jacktook"), patch(
        "lib.api.trakt.trakt.ADDON_VERSION", "1.15.0"
    ):
        result, _dialog, _failure, post, _sleep = run_poll(api, [response(200, token)])

    assert result == token
    assert post.call_args.kwargs["headers"] == {
        "Content-Type": "application/json",
        "trakt-api-version": "2",
        "trakt-api-key": "client-id",
        "User-Agent": "Jacktook/1.15.0",
    }


@pytest.mark.parametrize(
    ("status_code", "message"),
    [
        (404, "invalid"),
        (409, "already used"),
        (410, "expired"),
        (418, "denied"),
    ],
)
def test_terminal_device_status_stops_with_actionable_failure(status_code, message):
    api = TraktAuthentication()
    result, dialog, failure, post, _sleep = run_poll(api, [response(status_code)])

    assert result is None
    post.assert_called_once()
    assert message in failure.call_args.args[0].lower()
    dialog.close_dialog.assert_called_once_with()


def test_rate_limit_backs_off_then_succeeds():
    api = TraktAuthentication()
    token = {"access_token": "access", "refresh_token": "refresh"}
    result, dialog, _failure, _post, sleep_mock = run_poll(
        api, [response(429), response(200, token)]
    )

    assert result == token
    assert sum(call.args[0] for call in sleep_mock.call_args_list) == 3000
    assert max(call.args[0] for call in sleep_mock.call_args_list) <= 250
    dialog.close_dialog.assert_called_once_with()


def test_polling_stops_at_expiry():
    api = TraktAuthentication()
    result, dialog, failure, post, _sleep = run_poll(
        api, [response(400)], code=device_code(expires_in=2)
    )

    assert result is None
    post.assert_called_once()
    assert "expired" in failure.call_args.args[0].lower()
    dialog.close_dialog.assert_called_once_with()


@pytest.mark.parametrize("context_kwargs", [{"cancelled": True}, {"aborted": True}])
def test_polling_cancellation_stops_without_failure(context_kwargs):
    api = TraktAuthentication()
    result, dialog, failure, post, _sleep = run_poll(api, [], **context_kwargs)

    assert result is None
    post.assert_not_called()
    failure.assert_not_called()
    dialog.close_dialog.assert_called_once_with()


@pytest.mark.parametrize(
    "context_kwargs",
    [{"cancel_during_wait": True}, {"abort_during_wait": True}],
)
def test_polling_cancellation_during_wait_stops_promptly(context_kwargs):
    api = TraktAuthentication()
    result, dialog, failure, post, sleep_mock = run_poll(
        api, [], code=device_code(interval=60), **context_kwargs
    )

    assert result is None
    post.assert_not_called()
    failure.assert_not_called()
    sleep_mock.assert_called_once_with(250)
    dialog.close_dialog.assert_called_once_with()


def test_polling_transport_failure_is_reported_and_dialog_closes():
    api = TraktAuthentication()
    error = requests.ConnectionError("offline")
    result, dialog, failure, post, _sleep = run_poll(api, [error])

    assert result is None
    post.assert_called_once()
    assert "offline" in failure.call_args.args[0]
    dialog.close_dialog.assert_called_once_with()


def test_malformed_success_is_reported_and_dialog_closes():
    api = TraktAuthentication()
    malformed = response(200)
    malformed.json.side_effect = ValueError("invalid json")
    result, dialog, failure, post, _sleep = run_poll(api, [malformed])

    assert result is None
    post.assert_called_once()
    assert "invalid token response" in failure.call_args.args[0].lower()
    dialog.close_dialog.assert_called_once_with()
