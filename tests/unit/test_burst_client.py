from unittest.mock import MagicMock, patch

import pytest

from lib.jacktook.client import Burst
from lib.domain.torrent import TorrentStream


@pytest.fixture
def burst_client():
    return Burst(notification=MagicMock())


class MockProviderResult:
    def __init__(self, title, guid, indexer, seeders, peers, size):
        self.title = title
        self.guid = guid
        self.indexer = indexer
        self.seeders = seeders
        self.peers = peers
        self.size = size


def test_parse_response_valid_results(burst_client):
    results = [
        MockProviderResult(
            title="Movie 2024 1080p",
            guid="magnet:?xt=urn:btih:abc123",
            indexer="1337x",
            seeders=100,
            peers=50,
            size="1.5 GB",
        ),
        MockProviderResult(
            title="Movie 2024 720p",
            guid="magnet:?xt=urn:btih:def456",
            indexer="ThePirateBay",
            seeders=50,
            peers=25,
            size="800 MB",
        ),
    ]

    parsed = burst_client.parse_response(results)

    assert len(parsed) == 2
    assert parsed[0].title == "Movie 2024 1080p"
    assert parsed[0].seeders == 100
    assert parsed[0].peers == 50
    assert parsed[0].size == 1610612736  # 1.5 GB in bytes
    assert parsed[0].indexer == "Burst"
    assert parsed[0].provider == "1337x"
    assert parsed[1].title == "Movie 2024 720p"
    assert parsed[1].size == 838860800  # 800 MB in bytes


def test_parse_response_with_none_seeders_peers(burst_client):
    results = [
        MockProviderResult(
            title="Movie None Seeds",
            guid="magnet:?xt=urn:btih:abc123",
            indexer="1337x",
            seeders=None,
            peers=None,
            size="500 MB",
        ),
    ]

    parsed = burst_client.parse_response(results)

    assert len(parsed) == 1
    assert parsed[0].seeders == 0
    assert parsed[0].peers == 0
    assert parsed[0].size == 524288000


def test_parse_response_with_string_seeders_peers(burst_client):
    results = [
        MockProviderResult(
            title="Movie String Seeds",
            guid="magnet:?xt=urn:btih:abc123",
            indexer="1337x",
            seeders="42",
            peers="21",
            size="1 GB",
        ),
    ]

    parsed = burst_client.parse_response(results)

    assert len(parsed) == 1
    assert parsed[0].seeders == 42
    assert parsed[0].peers == 21


@patch("lib.clients.base.notification")
def test_parse_response_with_invalid_seeders_skips_result(mock_notification):
    burst_client = Burst(notification=MagicMock())
    results = [
        MockProviderResult(
            title="Valid Movie",
            guid="magnet:?xt=urn:btih:abc123",
            indexer="1337x",
            seeders=10,
            peers=5,
            size="1 GB",
        ),
        MockProviderResult(
            title="Invalid Seeds Movie",
            guid="magnet:?xt=urn:btih:def456",
            indexer="TPB",
            seeders="1000+",  # Invalid int conversion
            peers="50",
            size="2 GB",
        ),
        MockProviderResult(
            title="Another Valid",
            guid="magnet:?xt=urn:btih:ghi789",
            indexer="RARBG",
            seeders=20,
            peers=10,
            size="3 GB",
        ),
    ]

    parsed = burst_client.parse_response(results)

    assert len(parsed) == 2
    assert parsed[0].title == "Valid Movie"
    assert parsed[1].title == "Another Valid"
    mock_notification.assert_called_once()


def test_parse_response_with_none_size(burst_client):
    results = [
        MockProviderResult(
            title="Movie No Size",
            guid="magnet:?xt=urn:btih:abc123",
            indexer="1337x",
            seeders=10,
            peers=5,
            size=None,
        ),
    ]

    parsed = burst_client.parse_response(results)

    assert len(parsed) == 1
    assert parsed[0].size == 0


def test_parse_response_with_empty_size(burst_client):
    results = [
        MockProviderResult(
            title="Movie Empty Size",
            guid="magnet:?xt=urn:btih:abc123",
            indexer="1337x",
            seeders=10,
            peers=5,
            size="",
        ),
    ]

    parsed = burst_client.parse_response(results)

    assert len(parsed) == 1
    assert parsed[0].size == 0


def test_parse_response_empty_input(burst_client):
    parsed = burst_client.parse_response([])
    assert parsed == []


def test_parse_response_returns_torrent_stream_instances(burst_client):
    results = [
        MockProviderResult(
            title="Test",
            guid="magnet:?xt=urn:btih:abc123",
            indexer="1337x",
            seeders=1,
            peers=1,
            size="100 MB",
        ),
    ]

    parsed = burst_client.parse_response(results)

    assert len(parsed) == 1
    assert isinstance(parsed[0], TorrentStream)
