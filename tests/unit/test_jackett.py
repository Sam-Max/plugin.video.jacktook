import pytest
from unittest.mock import MagicMock, patch
import os
import sys

# Ensure mocks are loaded before importing the module under test
# This is crucial because 'lib.clients.jackett' imports 'xbmc' at the top level
sys.modules["xbmc"] = MagicMock()
sys.modules["xbmcgui"] = MagicMock()
sys.modules["xbmcaddon"] = MagicMock()

from lib.clients.jackett import Jackett
from lib.domain.torrent import TorrentStream

# Load fixture data
FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "../fixtures/jackett_response.xml"
)
with open(FIXTURE_PATH, "r") as f:
    XML_RESPONSE = f.read()


@pytest.fixture
def jackett_client():
    # Mock notification function
    mock_notification = MagicMock()
    mock_session = MagicMock()
    # Mock settings
    with patch("lib.clients.jackett.get_jackett_timeout", return_value=10):
        client = Jackett(
            host="http://localhost",
            apikey="testapikey",
            port="9117",
            notification=mock_notification,
            session=mock_session,
        )
    return client


def test_jackett_initialization(jackett_client):
    assert jackett_client.host == "http://localhost"
    assert jackett_client.apikey == "testapikey"
    assert "9117" in jackett_client.base_url


@patch("lib.clients.jackett.get_setting", return_value=False)  # Disable season packs
@patch("lib.clients.jackett.get_jackett_timeout", return_value=10)
def test_search_movie(mock_timeout, mock_get_setting, jackett_client):
    # Setup mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = XML_RESPONSE.encode("utf-8")

    # Configure injected mock session
    jackett_client.session.get.return_value = mock_response

    results = jackett_client.search("Big Buck Bunny", "movies")

    assert results is not None
    assert len(results) == 2

    # Verify first result
    res1 = results[0]
    assert isinstance(res1, TorrentStream)
    assert res1.title == "Big Buck Bunny 1080p"
    assert res1.seeders == 100
    assert res1.peers == 200
    assert res1.size == "1073741824"
    assert res1.indexer == "Jackett"
    assert res1.infoHash == "1234567890abcdef1234567890abcdef12345678"


@patch("lib.clients.jackett.get_setting", return_value=True)  # Enable season packs
@patch("lib.clients.jackett.get_jackett_timeout", return_value=10)
def test_search_tv_show(mock_timeout, mock_get_setting, jackett_client):
    # Setup mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = XML_RESPONSE.encode("utf-8")

    # Configure injected mock session
    jackett_client.session.get.return_value = mock_response

    # Search for S01E01
    results = jackett_client.search("Big Buck Bunny", "tv", season=1, episode=1)

    assert results is not None
    # Should call twice: once for episode, once for season pack
    assert jackett_client.session.get.call_count == 2
    # Results are extended from both calls (duplicate xml used for simplicity)
    assert len(results) == 4


def test_parse_response_error(jackett_client):
    mock_response = MagicMock()
    mock_response.content = b"Invalid XML"

    results = jackett_client.parse_response(mock_response)
    assert results is None


def test_extract_result(jackett_client):
    item = {
        "title": "Test Title",
        "link": "magnet:?xt=urn:btih:hash",
        "size": "100",
        "pubDate": "2023-01-01",
        "jackettindexer": {"#text": "Tracker"},
        "torznab:attr": [
            {"@name": "seeders", "@value": "10"},
            {"@name": "peers", "@value": "5"},
            {"@name": "infohash", "@value": "hash"},
        ],
    }

    results = []
    jackett_client.extract_result(results, item)

    assert len(results) == 1
    res = results[0]
    assert res.title == "Test Title"
    assert res.seeders == 10
    assert res.peers == 5
