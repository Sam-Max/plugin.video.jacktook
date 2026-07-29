import time
from unittest.mock import Mock, patch

import requests

from lib.api.trakt.trakt import TraktBase


def _unauthorized_response():
    response = Mock(status_code=401, headers={}, text="Unauthorized")
    response.raise_for_status.side_effect = requests.HTTPError(response=response)
    return response


def test_public_unauthenticated_401_preserves_existing_session():
    trakt = TraktBase()
    trakt._send_request = Mock(return_value=_unauthorized_response())

    with patch("lib.api.trakt.trakt.trakt_client", return_value="client-id"), patch.object(
        trakt, "_handle_unauthorized"
    ) as handle_unauthorized:
        result = trakt.call_trakt("movies/trending", with_auth=False)

    assert result == []
    handle_unauthorized.assert_not_called()


def test_bearer_authenticated_401_invalidates_session():
    trakt = TraktBase()
    trakt._send_request = Mock(return_value=_unauthorized_response())

    with patch("lib.api.trakt.trakt.trakt_client", return_value="client-id"), patch(
        "lib.api.trakt.trakt.get_property", return_value="access-token"
    ), patch.object(trakt, "ensure_token_valid"), patch.object(
        trakt, "_handle_unauthorized"
    ) as handle_unauthorized:
        result = trakt.call_trakt("users/me", with_auth=True)

    assert result == []
    handle_unauthorized.assert_called_once_with()
    assert trakt._send_request.call_args.args[3]["Authorization"] == "Bearer access-token"


def test_refresh_failure_invalidates_once_and_aborts_original_request():
    trakt = TraktBase()
    trakt._send_request = Mock(return_value=_unauthorized_response())

    properties = {
        "trakt_expires": str(time.time()),
        "trakt_refresh": "refresh-token",
        "trakt_token": "stale-access-token",
    }
    with patch("lib.api.trakt.trakt.trakt_client", return_value="client-id"), patch(
        "lib.api.trakt.trakt.trakt_secret", return_value="client-secret"
    ), patch("lib.api.trakt.trakt.get_property", side_effect=properties.get), patch.object(
        trakt, "_handle_unauthorized"
    ) as handle_unauthorized:
        result = trakt.call_trakt("users/me", with_auth=True)

    assert result == []
    handle_unauthorized.assert_called_once_with()
    trakt._send_request.assert_called_once()
    assert trakt._send_request.call_args.args[0] == "oauth/token"
