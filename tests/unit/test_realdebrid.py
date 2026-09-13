import json
import os
from base64 import b64encode
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from lib.api.debrid.base import ProviderException
from lib.api.debrid.realdebrid import RealDebrid

# Load fixture data
FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "../fixtures/realdebrid_response.json")
with open(FIXTURE_PATH) as f:
    JSON_DATA = json.load(f)


@pytest.fixture
def rd_client():
    mock_session = MagicMock()
    with patch.object(RealDebrid, "decode_token_str", return_value={"private_token": "secret"}):
        client = RealDebrid(token="test_token", session=mock_session)
        client.headers = {"Authorization": f"Bearer {client.token}"}
        return client


def test_realdebrid_api(rd_client):
    # Test get_user
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = JSON_DATA["user"]
    # The base class uses session.request(method=...)
    rd_client.session.request.return_value = mock_response

    user = rd_client.get_user()
    assert user["username"] == "testuser"
    assert user["type"] == "premium"

    # Test add_magnet_link
    mock_response.json.return_value = JSON_DATA["addMagnet"]

    magnet = "magnet:?xt=urn:btih:123"
    response = rd_client.add_magnet_link(magnet)
    assert response["id"] == "NEWTORRENT456"

    # Test get_user_torrent_list
    mock_response.json.return_value = JSON_DATA["torrents"]
    torrents = rd_client.get_user_torrent_list()
    assert len(torrents) == 1
    assert torrents[0]["status"] == "downloaded"


def test_get_user_torrent_list_passes_filter_param(rd_client):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = JSON_DATA["torrents"]
    rd_client.session.request.return_value = mock_response

    rd_client.get_user_torrent_list(filter="active")

    _, request_kwargs = rd_client.session.request.call_args
    assert request_kwargs["params"] == {"filter": "active"}


def test_get_user_torrent_list_without_filter_omits_param(rd_client):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = JSON_DATA["torrents"]
    rd_client.session.request.return_value = mock_response

    rd_client.get_user_torrent_list()

    _, request_kwargs = rd_client.session.request.call_args
    assert "filter" not in request_kwargs["params"]


def test_decode_token_str_accepts_a_token_without_padding():
    token = RealDebrid.encode_token_data("client-id", "client-secret", "refresh-token")
    assert token.endswith("=")
    stripped = token.rstrip("=")

    decoded = RealDebrid.decode_token_str(stripped)

    assert decoded == {
        "client_id": "client-id",
        "client_secret": "client-secret",
        "code": "refresh-token",
    }


def test_decode_token_str_ignores_stray_whitespace():
    token = RealDebrid.encode_token_data("client-id", "client-secret", "refresh-token")
    wrapped = " \n".join([token[:10], token[10:]])

    decoded = RealDebrid.decode_token_str(wrapped)

    assert decoded == {
        "client_id": "client-id",
        "client_secret": "client-secret",
        "code": "refresh-token",
    }


def test_decode_token_str_rejects_a_token_with_the_wrong_shape():
    token = b64encode(b"only:two").decode()

    with pytest.raises(ProviderException, match="Invalid token"):
        RealDebrid.decode_token_str(token)


def test_create_download_link_raises_when_the_response_has_no_download(rd_client):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"error": "no download"}
    rd_client.session.request.return_value = mock_response

    with pytest.raises(ProviderException, match="Failed to create download link"):
        rd_client.create_download_link("https://real-debrid.com/d/123")


def test_create_download_link_maps_a_2xx_error_code_to_its_message(rd_client):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"error": "traffic", "error_code": 23}
    rd_client.session.request.return_value = mock_response

    with pytest.raises(ProviderException, match="Traffic exhausted"):
        rd_client.create_download_link("https://real-debrid.com/d/123")


def test_days_remaining_compares_against_an_aware_utc_now(rd_client):
    expiration = (datetime.now(timezone.utc) + timedelta(days=5, hours=1)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    rd_client.get_user = MagicMock(return_value={"expiration": expiration})

    assert rd_client.days_remaining() == 5
