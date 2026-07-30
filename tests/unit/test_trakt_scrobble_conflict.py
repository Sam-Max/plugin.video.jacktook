from unittest.mock import Mock, patch

import pytest
import requests

from lib.api.trakt.trakt import ProviderException, TraktBase


def response(status_code, payload=None):
    result = Mock(status_code=status_code, headers={}, text="response body")
    result.json.return_value = payload if payload is not None else {}
    if status_code >= 400:
        result.raise_for_status.side_effect = requests.HTTPError(response=result)
    return result


def test_duplicate_stop_conflict_is_logged_without_exception_or_notification():
    api = TraktBase()
    api._send_request = Mock(return_value=response(409))
    with patch("lib.api.trakt.trakt.trakt_client", return_value="client-id"), patch(
        "lib.api.trakt.trakt.kodilog"
    ) as log, patch("lib.api.trakt.trakt.notification") as notification, patch(
        "lib.api.trakt.trakt.ProviderException"
    ) as provider_exception:
        result = api.call_trakt(
            "scrobble/stop", data={"progress": 100}, with_auth=False
        )

    assert result is None
    log.assert_any_call(
        "Trakt duplicate scrobble/stop conflict ignored (HTTP 409)", level=0
    )
    provider_exception.assert_not_called()
    notification.assert_not_called()


def test_successful_stop_response_is_preserved():
    api = TraktBase()
    payload = {"action": "scrobble", "progress": 100}
    api._send_request = Mock(return_value=response(200, payload))
    with patch("lib.api.trakt.trakt.trakt_client", return_value="client-id"):
        result = api.call_trakt(
            "scrobble/stop", data={"progress": 100}, with_auth=False
        )

    assert result == payload


@pytest.mark.parametrize(
    ("path", "method", "data"),
    [
        ("scrobble/start", None, {"progress": 100}),
        ("scrobble/stop/duplicate", None, {"progress": 100}),
        ("scrobble/stop", "delete", {"progress": 100}),
        ("scrobble/stop", None, None),
    ],
)
def test_other_conflicts_still_raise_and_notify(path, method, data):
    api = TraktBase()
    api._send_request = Mock(return_value=response(409))
    with patch("lib.api.trakt.trakt.trakt_client", return_value="client-id"), patch(
        "lib.api.trakt.trakt.notification"
    ) as notification, pytest.raises(ProviderException, match="HTTP Error: 409"):
        api.call_trakt(
            path,
            data=data,
            method=method,
            with_auth=False,
        )

    notification.assert_called_once_with("Trakt API error: HTTP Error: 409")
