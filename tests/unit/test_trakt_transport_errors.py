from unittest.mock import Mock, patch

import pytest
import requests
import xbmc

from lib.api.trakt.trakt import ProviderException, TraktBase


def _response(status_code=200, payload=None, headers=None):
    response = Mock(
        status_code=status_code,
        headers=headers or {},
        text="response body",
    )
    response.json.return_value = payload if payload is not None else {}
    if status_code >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(response=response)
    return response


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("lists/trending", "lists_trending"),
        ("lists/popular", "lists_popular"),
        ("lists/private-list-id/items?extended=full", "list_items_by_id"),
        ("users/private-user/lists/private-slug/items", "list_items_by_user"),
        ("lists//items", "other"),
        ("users//lists//items", "other"),
        ("movies/trending", "other"),
        (None, "other"),
    ],
)
def test_safe_route_label_returns_only_redacted_fixed_categories(path, expected):
    label = TraktBase._safe_route_label(path)

    assert label == expected
    assert label in {
        "lists_trending",
        "lists_popular",
        "list_items_by_id",
        "list_items_by_user",
        "other",
    }
    for sensitive_value in ("private-list-id", "private-user", "private-slug", "extended"):
        assert sensitive_value not in label


@pytest.mark.parametrize(
    "transport_error",
    [
        requests.Timeout("timed out"),
        requests.ConnectionError(
            "request failed for https://api.trakt.tv/users/private-user/lists/private-slug/items"
        ),
    ],
)
def test_initial_transport_failure_is_normalized(transport_error):
    trakt = TraktBase()
    trakt._send_request = Mock(side_effect=transport_error)

    with patch("lib.api.trakt.trakt.trakt_client", return_value="client-id"), patch(
        "lib.api.trakt.trakt.notification"
    ), patch(
        "lib.api.trakt.trakt.kodilog"
    ) as kodilog, pytest.raises(ProviderException, match="Trakt API request failed") as exc_info:
        trakt.call_trakt(
            "users/private-user/lists/private-slug/items", with_auth=False
        )

    assert exc_info.value.__cause__ is transport_error
    kodilog.assert_called_once_with(
        "Trakt API transport error [route=list_items_by_user]", level=xbmc.LOGERROR
    )


def test_retry_transport_failure_is_normalized():
    transport_error = requests.ConnectionError("retry connection failed")
    trakt = TraktBase()
    trakt._send_request = Mock(
        side_effect=[_response(429, headers={"Retry-After": "0"}), transport_error]
    )

    with patch("lib.api.trakt.trakt.trakt_client", return_value="client-id"), patch(
        "lib.api.trakt.trakt.notification"
    ), patch.object(trakt, "_wait_for_retry", return_value=True) as wait, pytest.raises(
        ProviderException, match="Trakt API request failed"
    ) as exc_info:
        trakt.call_trakt("movies/trending", with_auth=False)

    assert exc_info.value.__cause__ is transport_error
    assert trakt._send_request.call_count == 2
    wait.assert_called_once_with(0)


@pytest.mark.parametrize("status_code", [502, 503, 504])
def test_overload_status_retries_once_after_default_delay(status_code):
    trakt = TraktBase()
    trakt._send_request = Mock(side_effect=[_response(status_code), _response(payload={"ok": True})])

    with patch("lib.api.trakt.trakt.trakt_client", return_value="client-id"), patch.object(
        trakt, "_wait_for_retry", return_value=True
    ) as wait:
        assert trakt.call_trakt("movies/trending", with_auth=False) == {"ok": True}

    assert trakt._send_request.call_count == 2
    wait.assert_called_once_with(30)


@pytest.mark.parametrize(
    ("retry_after", "expected_delay"),
    [
        ("12.5", 12.5),
        ("invalid", 30),
        ("-1", 30),
        ("NaN", 30),
        ("Infinity", 30),
        ("120", 60),
    ],
)
def test_overload_retry_after_is_validated_and_capped(retry_after, expected_delay):
    trakt = TraktBase()
    trakt._send_request = Mock(
        side_effect=[
            _response(503, headers={"Retry-After": retry_after}),
            _response(payload={"ok": True}),
        ]
    )

    with patch("lib.api.trakt.trakt.trakt_client", return_value="client-id"), patch.object(
        trakt, "_wait_for_retry", return_value=True
    ) as wait:
        assert trakt.call_trakt("movies/trending", with_auth=False) == {"ok": True}

    wait.assert_called_once_with(expected_delay)


@pytest.mark.parametrize(
    ("retry_after", "expected_delay"), [("invalid", 1), ("120", 60)]
)
def test_rate_limit_retry_after_is_validated_and_capped(retry_after, expected_delay):
    trakt = TraktBase()
    trakt._send_request = Mock(
        side_effect=[
            _response(429, headers={"Retry-After": retry_after}),
            _response(payload={"ok": True}),
        ]
    )

    with patch("lib.api.trakt.trakt.trakt_client", return_value="client-id"), patch.object(
        trakt, "_wait_for_retry", return_value=True
    ) as wait:
        assert trakt.call_trakt("movies/trending", with_auth=False) == {"ok": True}

    wait.assert_called_once_with(expected_delay)


def test_overload_retry_cancellation_preserves_controlled_http_error():
    trakt = TraktBase()
    trakt._send_request = Mock(return_value=_response(503))
    monitor = Mock()
    monitor.abortRequested.return_value = True

    with patch("lib.api.trakt.trakt.trakt_client", return_value="client-id"), patch(
        "lib.api.trakt.trakt.xbmc.Monitor", return_value=monitor
    ), patch("lib.api.trakt.trakt.sleep") as sleep, pytest.raises(
        ProviderException, match="Trakt API error: Service Unavailable"
    ):
        trakt.call_trakt("movies/trending", with_auth=False)

    trakt._send_request.assert_called_once()
    sleep.assert_not_called()


def test_rate_limit_retry_cancellation_preserves_controlled_http_error():
    trakt = TraktBase()
    trakt._send_request = Mock(return_value=_response(429, headers={"Retry-After": "30"}))
    monitor = Mock()
    monitor.abortRequested.return_value = True

    with patch("lib.api.trakt.trakt.trakt_client", return_value="client-id"), patch(
        "lib.api.trakt.trakt.xbmc.Monitor", return_value=monitor
    ), patch("lib.api.trakt.trakt.sleep") as sleep, pytest.raises(
        ProviderException, match="Trakt API error: Rate Limit Exceeded"
    ):
        trakt.call_trakt("movies/trending", with_auth=False)

    trakt._send_request.assert_called_once()
    sleep.assert_not_called()


def test_overload_wait_checks_abort_between_short_slices():
    monitor = Mock()
    monitor.abortRequested.side_effect = [False, True]

    with patch("lib.api.trakt.trakt.xbmc.Monitor", return_value=monitor), patch(
        "lib.api.trakt.trakt.time.monotonic", return_value=0
    ), patch("lib.api.trakt.trakt.sleep") as sleep:
        assert TraktBase._wait_for_retry(30) is False

    sleep.assert_called_once_with(250)


def test_overload_retry_transport_failure_is_normalized():
    transport_error = requests.ConnectionError("retry connection failed")
    trakt = TraktBase()
    trakt._send_request = Mock(side_effect=[_response(502), transport_error])

    with patch("lib.api.trakt.trakt.trakt_client", return_value="client-id"), patch.object(
        trakt, "_wait_for_retry", return_value=True
    ), pytest.raises(ProviderException, match="Trakt API request failed") as exc_info:
        trakt.call_trakt("movies/trending", with_auth=False)

    assert exc_info.value.__cause__ is transport_error
    assert trakt._send_request.call_count == 2


def test_unrelated_5xx_is_not_retried():
    trakt = TraktBase()
    trakt._send_request = Mock(return_value=_response(500))

    with patch("lib.api.trakt.trakt.trakt_client", return_value="client-id"), patch.object(
        trakt, "_wait_for_retry"
    ) as wait, pytest.raises(ProviderException, match="Internal Server Error"):
        trakt.call_trakt("movies/trending", with_auth=False)

    trakt._send_request.assert_called_once()
    wait.assert_not_called()


@pytest.mark.parametrize(
    "responses",
    [
        [_response(429, headers={"Retry-After": "0"}), _response(503)],
        [_response(503), _response(429, headers={"Retry-After": "0"})],
    ],
)
def test_rate_limit_and_overload_share_one_retry_budget(responses):
    trakt = TraktBase()
    trakt._send_request = Mock(side_effect=responses)

    with patch("lib.api.trakt.trakt.trakt_client", return_value="client-id"), patch.object(
        trakt, "_wait_for_retry", return_value=True
    ) as wait, pytest.raises(
        ProviderException
    ):
        trakt.call_trakt("movies/trending", with_auth=False)

    assert trakt._send_request.call_count == 2
    if responses[0].status_code == 429:
        wait.assert_called_once_with(0)
    else:
        wait.assert_called_once_with(30)


@pytest.mark.parametrize(
    ("data", "is_delete", "method", "status_code"),
    [
        ({"movies": []}, False, None, 429),
        ({"movies": []}, False, None, 503),
        (None, False, "post", 503),
        (None, False, "delete", 503),
        (None, True, None, 503),
    ],
)
def test_mutation_requests_are_not_retried(data, is_delete, method, status_code):
    trakt = TraktBase()
    trakt._send_request = Mock(return_value=_response(status_code))

    with patch("lib.api.trakt.trakt.trakt_client", return_value="client-id"), patch.object(
        trakt, "_wait_for_retry"
    ) as wait, pytest.raises(ProviderException):
        trakt.call_trakt(
            "sync/watchlist", data=data, is_delete=is_delete, method=method, with_auth=False
        )

    trakt._send_request.assert_called_once()
    wait.assert_not_called()


def test_successful_response_processing_is_preserved():
    trakt = TraktBase()
    trakt._send_request = Mock(return_value=_response(payload={"title": "Movie"}))

    with patch("lib.api.trakt.trakt.trakt_client", return_value="client-id"):
        result = trakt.call_trakt("movies/1", with_auth=False)

    assert result == {"title": "Movie"}


def test_http_error_handling_is_preserved():
    trakt = TraktBase()
    trakt._send_request = Mock(side_effect=[_response(503), _response(503)])

    with patch("lib.api.trakt.trakt.trakt_client", return_value="client-id"), patch(
        "lib.api.trakt.trakt.notification"
    ), patch.object(
        trakt, "_wait_for_retry", return_value=True
    ), pytest.raises(ProviderException, match="Trakt API error: Service Unavailable") as exc_info:
        trakt.call_trakt("movies/trending", with_auth=False)

    assert isinstance(exc_info.value.__cause__, requests.HTTPError)


def test_non_overload_http_failure_logs_at_error_level():
    trakt = TraktBase()
    trakt._send_request = Mock(return_value=_response(400))

    with patch("lib.api.trakt.trakt.trakt_client", return_value="client-id"), patch(
        "lib.api.trakt.trakt.kodilog"
    ) as kodilog, pytest.raises(
        ProviderException, match="Trakt API error: Bad Request"
    ) as exc_info:
        trakt.call_trakt("lists/private-list-id/items", with_auth=False)

    assert exc_info.value.user_message == "Trakt request failed"
    kodilog.assert_any_call(
        "Trakt API error [route=list_items_by_id] (HTTP 400): response body",
        level=xbmc.LOGERROR,
    )
