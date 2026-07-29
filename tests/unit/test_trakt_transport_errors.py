from unittest.mock import Mock, patch

import pytest
import requests

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
    "transport_error",
    [requests.Timeout("timed out"), requests.ConnectionError("connection failed")],
)
def test_initial_transport_failure_is_normalized(transport_error):
    trakt = TraktBase()
    trakt._send_request = Mock(side_effect=transport_error)

    with patch("lib.api.trakt.trakt.trakt_client", return_value="client-id"), patch(
        "lib.api.trakt.trakt.notification"
    ), pytest.raises(ProviderException, match=f"Trakt API error: {transport_error}") as exc_info:
        trakt.call_trakt("movies/trending", with_auth=False)

    assert exc_info.value.__cause__ is transport_error


def test_retry_transport_failure_is_normalized():
    transport_error = requests.ConnectionError("retry connection failed")
    trakt = TraktBase()
    trakt._send_request = Mock(
        side_effect=[_response(429, headers={"Retry-After": "0"}), transport_error]
    )

    with patch("lib.api.trakt.trakt.trakt_client", return_value="client-id"), patch(
        "lib.api.trakt.trakt.notification"
    ), patch("lib.api.trakt.trakt.sleep") as sleep, pytest.raises(
        ProviderException, match="Trakt API error: retry connection failed"
    ) as exc_info:
        trakt.call_trakt("movies/trending", with_auth=False)

    assert exc_info.value.__cause__ is transport_error
    assert trakt._send_request.call_count == 2
    sleep.assert_called_once_with(0)


def test_successful_response_processing_is_preserved():
    trakt = TraktBase()
    trakt._send_request = Mock(return_value=_response(payload={"title": "Movie"}))

    with patch("lib.api.trakt.trakt.trakt_client", return_value="client-id"):
        result = trakt.call_trakt("movies/1", with_auth=False)

    assert result == {"title": "Movie"}


def test_http_error_handling_is_preserved():
    trakt = TraktBase()
    trakt._send_request = Mock(return_value=_response(503))

    with patch("lib.api.trakt.trakt.trakt_client", return_value="client-id"), patch(
        "lib.api.trakt.trakt.notification"
    ), pytest.raises(ProviderException, match="Trakt API error: Service Unavailable") as exc_info:
        trakt.call_trakt("movies/trending", with_auth=False)

    assert isinstance(exc_info.value.__cause__, requests.HTTPError)
