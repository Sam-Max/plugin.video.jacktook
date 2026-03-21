from unittest.mock import MagicMock, patch

from lib.utils.debrid.debrid_utils import get_magnet_from_uri


def test_get_magnet_from_uri_follows_redirect_to_magnet():
    redirect_response = MagicMock()
    redirect_response.status_code = 302
    redirect_response.headers = {
        "Location": "magnet:?xt=urn:btih:1234567890ABCDEF1234567890ABCDEF12345678&dn=Test"
    }

    with patch(
        "lib.utils.debrid.debrid_utils.requests.get", return_value=redirect_response
    ) as mock_get:
        magnet, info_hash, torrent_url = get_magnet_from_uri(
            "https://jackett.local/dl/test"
        )

    assert magnet.startswith("magnet:?xt=urn:btih:1234567890ABCDEF")
    assert info_hash == "1234567890abcdef1234567890abcdef12345678"
    assert torrent_url == ""
    mock_get.assert_called_once()


def test_get_magnet_from_uri_follows_http_redirect_chain():
    first_response = MagicMock()
    first_response.status_code = 302
    first_response.headers = {"Location": "/download/next"}

    second_response = MagicMock()
    second_response.status_code = 302
    second_response.headers = {
        "Location": "magnet:?xt=urn:btih:ABCDEF1234567890ABCDEF1234567890ABCDEF12&dn=Test"
    }

    with patch(
        "lib.utils.debrid.debrid_utils.requests.get",
        side_effect=[first_response, second_response],
    ) as mock_get:
        magnet, info_hash, torrent_url = get_magnet_from_uri(
            "https://jackett.local/dl/test"
        )

    assert magnet.startswith("magnet:?xt=urn:btih:ABCDEF1234567890")
    assert info_hash == "abcdef1234567890abcdef1234567890abcdef12"
    assert torrent_url == ""
    assert mock_get.call_count == 2


def test_get_magnet_from_uri_preserves_torrent_url_for_playback():
    torrent_response = MagicMock()
    torrent_response.status_code = 200
    torrent_response.url = "https://jackett.local/download/file.torrent"
    torrent_response.content = b"torrent-bytes"

    with patch(
        "lib.utils.debrid.debrid_utils.requests.get", return_value=torrent_response
    ) as mock_get, patch(
        "lib.utils.debrid.debrid_utils.extract_torrent_metadata",
        return_value="magnet:?xt=urn:btih:AAAABBBBCCCCDDDDEEEEFFFF0000111122223333&dn=Test",
    ):
        magnet, info_hash, torrent_url = get_magnet_from_uri(
            "https://jackett.local/dl/test"
        )

    assert magnet == ""
    assert info_hash == "aaaabbbbccccddddeeeeffff0000111122223333"
    assert torrent_url == "https://jackett.local/dl/test"
    mock_get.assert_called_once()
