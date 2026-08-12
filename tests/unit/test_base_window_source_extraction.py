from unittest.mock import patch

import pytest

from lib.domain.torrent import TorrentStream
from lib.gui.base_window import BaseWindow
from lib.utils.general.utils import Indexer, IndexerType
from lib.utils.player import utils as player_utils


class _DummyWindow(BaseWindow):
    def handle_action(self, action_id, control_id=None):
        return None


def test_extract_source_details_prefers_torrent_url_over_magnet_candidate():
    source = TorrentStream(
        type=IndexerType.TORRENT,
        indexer=Indexer.JACKETT,
        url="https://jackett.local/dl/1",
    )

    window = _DummyWindow("dummy.xml", "")

    with patch(
        "lib.gui.base_window.get_magnet_from_uri",
        return_value=(
            "magnet:?xt=urn:btih:abc123",
            "abc123",
            "https://filelist.io/download.php?id=1",
        ),
    ):
        url, magnet, _ = window._extract_source_details(source)

    assert url == "https://filelist.io/download.php?id=1"
    assert magnet == ""


def test_extract_source_details_skips_infohash_fallback_when_http_url_exists():
    source = TorrentStream(
        type=IndexerType.TORRENT,
        indexer=Indexer.JACKETT,
        url="https://example.com/file.torrent",
        infoHash="abc123",
    )

    window = _DummyWindow("dummy.xml", "")
    url, magnet, _ = window._extract_source_details(source)

    assert url == "https://example.com/file.torrent"
    assert magnet == ""


def test_extract_source_details_uses_infohash_fallback_without_http_url():
    source = TorrentStream(
        type=IndexerType.TORRENT,
        indexer=Indexer.JACKETT,
        guid="urn:btih:abc123",
        infoHash="abc123",
    )

    window = _DummyWindow("dummy.xml", "")
    url, magnet, _ = window._extract_source_details(source)

    assert url == ""
    assert magnet == "magnet:?xt=urn:btih:abc123"


@pytest.mark.parametrize("mode", ["movies", "tv"])
def test_prepare_source_data_forwards_localized_overview_as_description(mode):
    synopsis = "Localized synopsis <b>without truncation</b>"
    source = TorrentStream(
        title="Selected source",
        type=IndexerType.TORRENT,
        indexer=Indexer.JACKETT,
    )
    window = _DummyWindow("dummy.xml", "")
    window.item_information = {"mode": mode, "overview": synopsis}

    playback_data = window.prepare_source_data(source, "", "", True)

    assert playback_data["description"] == synopsis


def test_prepare_source_data_uses_empty_description_when_overview_is_missing():
    source = TorrentStream(
        title="Selected source",
        type=IndexerType.TORRENT,
        indexer=Indexer.JACKETT,
    )
    window = _DummyWindow("dummy.xml", "")

    playback_data = window.prepare_source_data(source, "", "", True)

    assert playback_data["description"] == ""


@pytest.mark.parametrize(
    "source",
    [
        TorrentStream(
            title="Jackett result",
            type=IndexerType.TORRENT,
            indexer=Indexer.JACKETT,
            guid="magnet:?xt=urn:btih:jackett-hash",
            infoHash="jackett-hash",
        ),
        TorrentStream(
            title="Prowlarr result",
            type=IndexerType.TORRENT,
            indexer=Indexer.PROWLARR,
            url="magnet:?xt=urn:btih:prowlarr-hash",
            infoHash="prowlarr-hash",
        ),
        TorrentStream(
            title="External Scraper result",
            type=IndexerType.TORRENT,
            indexer=Indexer.EXTERNAL_SCRAPER,
            url="magnet:?xt=urn:btih:external-scraper-hash",
            infoHash="external-scraper-hash",
        ),
    ],
    ids=["jackett", "prowlarr", "external-scraper"],
)
def test_non_stremio_selected_sources_delegate_unchanged_to_legacy_resolver(monkeypatch, source):
    window = _DummyWindow("dummy.xml", "")
    expected = window.prepare_source_data(
        source, *window._extract_source_details(source), pack_select=False
    )
    resolver_calls = []

    monkeypatch.setattr(
        player_utils,
        "resolve_playback_url",
        lambda data: resolver_calls.append(data) or data,
    )

    assert window._ensure_playback_info(source) == expected
    assert resolver_calls == [expected]


def test_easynews_selected_source_uses_legacy_easynews_resolution_without_network(monkeypatch):
    source = TorrentStream(
        title="EasyNews result",
        type=IndexerType.DIRECT,
        indexer=Indexer.EASYNEWS,
        url="https://members.easynews.com/file.mkv",
    )
    window = _DummyWindow("dummy.xml", "")
    expected = window.prepare_source_data(
        source, *window._extract_source_details(source), pack_select=False
    )
    legacy_resolver = player_utils.resolve_playback_url
    resolver_calls = []
    easynews_payloads = []

    def resolve_with_easynews_branch(data):
        resolver_calls.append(dict(data))
        return legacy_resolver(data)

    monkeypatch.setattr(player_utils, "resolve_playback_url", resolve_with_easynews_branch)
    monkeypatch.setattr(
        player_utils,
        "get_easynews_url",
        lambda data: (
            easynews_payloads.append(dict(data)) or "https://resolved.easynews.example/file.mkv"
        ),
    )

    resolved = window._ensure_playback_info(source)

    assert resolver_calls == [expected]
    assert easynews_payloads == [expected]
    assert resolved["url"] == "https://resolved.easynews.example/file.mkv"
