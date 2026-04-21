from unittest.mock import patch

from lib.domain.torrent import TorrentStream
from lib.gui.base_window import BaseWindow
from lib.utils.general.utils import Indexer, IndexerType


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
