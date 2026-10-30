from lib.utils.general.utils import join_url_headers, split_url_headers


def test_split_url_headers_multiple():
    locator = (
        "https://tracker.example/download.php/1.torrent"
        "|Accept-Language=en-US,en;q=0.9"
        "|Referer=https://bitsearch.to/"
    )
    base, headers = split_url_headers(locator)

    assert base == "https://tracker.example/download.php/1.torrent"
    assert headers == {
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://bitsearch.to/",
    }
    assert join_url_headers(base, headers) == locator


def test_split_url_headers_without_suffix():
    assert split_url_headers("https://tracker.example/a.torrent") == (
        "https://tracker.example/a.torrent",
        {},
    )


def test_split_url_headers_ignores_malformed_chunks():
    base, headers = split_url_headers("https://tracker.example/a.torrent|broken|A=B")

    assert base == "https://tracker.example/a.torrent"
    assert headers == {"A": "B"}


def test_downloader_strips_every_header():
    from lib.downloader import Downloader

    downloader = Downloader(
        "https://tracker.example/a.torrent|Accept-Language=en|Referer=https://site/",
        "/tmp",
        "a.torrent",
        show_progress=False,
    )
    downloader._prepare_url()

    assert downloader.url == "https://tracker.example/a.torrent"
    assert downloader.headers == {
        "Accept-Language": "en",
        "Referer": "https://site/",
    }


def test_get_torrent_data_from_uri_parses_headers_and_preserves_suffix():
    from unittest.mock import MagicMock, patch

    from lib.utils.debrid import debrid_utils

    response = MagicMock(status_code=200, content=b"d8:announce", url="https://example.com/y.torrent", headers={})
    with patch.object(debrid_utils.requests, "get", return_value=response) as get, patch.object(
        debrid_utils, "extract_torrent_metadata", return_value="magnet:?xt=urn:btih:" + "a" * 40
    ), patch.object(debrid_utils, "get_info_hash_from_magnet", return_value="a" * 40):
        data, magnet, info_hash, torrent_url = debrid_utils.get_torrent_data_from_uri(
            "https://example.com/y.torrent|Referer=https://site/"
        )

    assert get.call_args.args[0] == "https://example.com/y.torrent"
    assert get.call_args.kwargs["headers"]["Referer"] == "https://site/"
    assert data == b"d8:announce"
    assert magnet.startswith("magnet:?xt=urn:btih:")
    assert info_hash == "a" * 40
    assert torrent_url == "https://example.com/y.torrent|Referer=https://site/"
