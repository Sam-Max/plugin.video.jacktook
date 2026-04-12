import pytest
from unittest.mock import MagicMock, patch

from lib.clients.prowlarr import Prowlarr


@pytest.fixture
def prowlarr_client():
    mock_notification = MagicMock()
    with patch("lib.clients.prowlarr.get_prowlarr_timeout", return_value=10):
        client = Prowlarr(
            host="http://localhost",
            apikey="testapikey",
            port="9696",
            notification=mock_notification,
        )
    return client


def test_prowlarr_initialization(prowlarr_client):
    assert prowlarr_client.base_url == "http://localhost:9696/api/v1/search"
    assert prowlarr_client.apikey == "testapikey"


def test_prowlarr_query_with_year_appended(prowlarr_client):
    with patch.object(prowlarr_client.session, "get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        with patch("lib.clients.prowlarr.get_prowlarr_timeout", return_value=10):
            prowlarr_client.search("Inception", "movies", year=2010)

        call_args = mock_get.call_args
        params = call_args[1]["params"]
        assert params["query"] == "Inception 2010"
        assert params["categories"] == [2000, 8000]


def test_prowlarr_query_without_year(prowlarr_client):
    with patch.object(prowlarr_client.session, "get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        with patch("lib.clients.prowlarr.get_prowlarr_timeout", return_value=10):
            prowlarr_client.search("Inception", "movies")

        call_args = mock_get.call_args
        params = call_args[1]["params"]
        assert params["query"] == "Inception"
        assert params["categories"] == [2000, 8000]


def test_prowlarr_search_variant_mapping(prowlarr_client):
    with patch.object(prowlarr_client.session, "get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        with patch("lib.clients.prowlarr.get_prowlarr_timeout", return_value=10):
            # Test with variant and year
            prowlarr_client.search(
                "Spirited Away", "movies", variant=None, year=2001
            )

        call_args = mock_get.call_args
        params = call_args[1]["params"]
        # Year should be appended to query for movies
        assert params["query"] == "Spirited Away 2001"


def test_prowlarr_year_not_appended_for_tv(prowlarr_client):
    with patch.object(prowlarr_client.session, "get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        with patch("lib.clients.prowlarr.get_prowlarr_timeout", return_value=10):
            with patch("lib.clients.prowlarr.get_setting", return_value=False):
                prowlarr_client.search("Breaking Bad", "tv", season=1, episode=1, year=2008)

        call_args = mock_get.call_args
        params = call_args[1]["params"]
        # Year should NOT be appended for TV shows
        assert "2008" not in params["query"]
        assert "S01E01" in params["query"]
