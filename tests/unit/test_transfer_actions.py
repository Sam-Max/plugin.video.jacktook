from unittest.mock import MagicMock, patch

from lib.utils.general.utils import DebridType
from lib.utils.debrid import debrid_utils
from lib.utils.torrent import torrserver_utils


def test_add_source_to_torrserver_uses_magnet_when_available():
    api = MagicMock()
    api.add_magnet.return_value = "abc123"

    with patch.object(torrserver_utils, "JACKTORR_ADDON", True), patch.object(
        torrserver_utils, "get_torrserver_api", return_value=api
    ), patch.object(torrserver_utils, "notification") as notification:
        result = torrserver_utils.add_source_to_torrserver(
            magnet="magnet:?xt=urn:btih:abc123", title="Test"
        )

    assert result == "abc123"
    api.add_magnet.assert_called_once_with(
        "magnet:?xt=urn:btih:abc123", title="Test", poster=""
    )
    notification.assert_called_once()


def test_add_source_to_torrserver_uploads_torrent_file_from_url():
    api = MagicMock()
    api.add_torrent_obj.return_value = "def456"
    response = MagicMock()
    response.content = b"torrent-bytes"
    response.raise_for_status.return_value = None

    with patch.object(torrserver_utils, "JACKTORR_ADDON", True), patch.object(
        torrserver_utils, "get_torrserver_api", return_value=api
    ), patch.object(torrserver_utils.requests, "get", return_value=response) as http_get:
        result = torrserver_utils.add_source_to_torrserver(url="https://example.com/test.torrent")

    assert result == "def456"
    http_get.assert_called_once()
    api.add_torrent_obj.assert_called_once()


def test_add_source_to_debrid_uses_preferred_enabled_service():
    helper = MagicMock()

    with patch.object(
        debrid_utils, "get_enabled_cloud_transfer_debrids", return_value=[DebridType.RD]
    ), patch.object(debrid_utils, "RealDebridHelper", return_value=helper), patch.object(
        debrid_utils, "notification"
    ) as notification:
        result = debrid_utils.add_source_to_debrid("abc123", DebridType.RD)

    assert result == DebridType.RD
    helper.add_magnet.assert_called_once_with("abc123")
    notification.assert_called_once()


def test_choose_debrid_for_transfer_prompts_when_multiple_supported_services_enabled():
    dialog = MagicMock()
    dialog.select.return_value = 1

    with patch.object(
        debrid_utils,
        "get_enabled_cloud_transfer_debrids",
        return_value=[DebridType.RD, DebridType.AD],
    ), patch.object(debrid_utils, "Dialog", return_value=dialog):
        selected = debrid_utils.choose_debrid_for_transfer()

    assert selected == DebridType.AD
    dialog.select.assert_called_once()
