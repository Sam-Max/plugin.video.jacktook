import pytest
from unittest.mock import MagicMock, patch
import os
import sys
import json

# Ensure mocks are loaded
sys.modules["xbmc"] = MagicMock()
sys.modules["xbmcgui"] = MagicMock()
sys.modules["xbmcaddon"] = MagicMock()

from lib.api.debrid.realdebrid import RealDebrid

# Load fixture data
FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "../fixtures/realdebrid_response.json"
)
with open(FIXTURE_PATH, "r") as f:
    JSON_DATA = json.load(f)


@pytest.fixture
def rd_client():
    mock_session = MagicMock()
    with patch.object(
        RealDebrid, "decode_token_str", return_value={"private_token": "secret"}
    ):
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
