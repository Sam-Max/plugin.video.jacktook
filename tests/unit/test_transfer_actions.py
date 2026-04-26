from unittest.mock import MagicMock, patch

from lib.clients.debrid.torbox import TorboxHelper
from lib.nav import debrid as debrid_navigation
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


def test_add_source_to_torrserver_saves_metadata_under_returned_and_source_hashes():
    api = MagicMock()
    api.add_magnet.return_value = "RETURNEDHASH"
    data = '{"title": "Test Movie", "ids": {"imdb_id": "tt123"}}'

    with patch.object(torrserver_utils, "JACKTORR_ADDON", True), patch.object(
        torrserver_utils, "get_torrserver_api", return_value=api
    ), patch.object(torrserver_utils, "notification"), patch.object(
        torrserver_utils, "get_info_hash_from_magnet", return_value="MAGNETHASH"
    ), patch.object(torrserver_utils, "save_torrent_meta") as mock_save:
        result = torrserver_utils.add_source_to_torrserver(
            magnet="magnet:?xt=urn:btih:MAGNETHASH",
            info_hash="SOURCEHASH",
            title="Test",
            data=data,
        )

    assert result == "RETURNEDHASH"
    saved_hashes = [call.args[0] for call in mock_save.call_args_list]
    assert saved_hashes == ["returnedhash", "sourcehash", "magnethash"]
    assert all(call.args[1]["ids"]["imdb_id"] == "tt123" for call in mock_save.call_args_list)


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


def test_add_source_to_torrserver_prefers_torrent_url_over_magnet():
    api = MagicMock()
    api.add_torrent_obj.return_value = "urlhash"
    response = MagicMock()
    response.content = b"torrent-bytes"
    response.raise_for_status.return_value = None

    with patch.object(torrserver_utils, "JACKTORR_ADDON", True), patch.object(
        torrserver_utils, "get_torrserver_api", return_value=api
    ), patch.object(torrserver_utils.requests, "get", return_value=response):
        result = torrserver_utils.add_source_to_torrserver(
            url="https://filelist.io/download.php?id=1",
            magnet="magnet:?xt=urn:btih:abc123",
        )

    assert result == "urlhash"
    api.add_torrent_obj.assert_called_once()
    api.add_magnet.assert_not_called()


def test_add_source_to_torrserver_falls_back_to_magnet_when_url_fails():
    api = MagicMock()
    api.add_magnet.return_value = "abc123"

    with patch.object(torrserver_utils, "JACKTORR_ADDON", True), patch.object(
        torrserver_utils, "get_torrserver_api", return_value=api
    ), patch.object(
        torrserver_utils.requests, "get", side_effect=Exception("network")
    ):
        result = torrserver_utils.add_source_to_torrserver(
            url="https://example.com/details/1",
            magnet="magnet:?xt=urn:btih:abc123",
        )

    assert result == "abc123"
    api.add_magnet.assert_called_once_with(
        "magnet:?xt=urn:btih:abc123", title="", poster=""
    )


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


def test_torbox_helper_get_cloud_downloads_returns_playable_items():
    helper = TorboxHelper()
    helper.client = MagicMock()
    helper.client.get_user_torrent_list.return_value = {
        "data": [
            {
                "id": "torrent-1",
                "name": "Torrent One",
                "download_present": True,
                "files": [
                    {"id": "file-1", "name": "sample.txt", "size": 1},
                    {"id": "file-2", "name": "video.mkv", "size": 10},
                ],
            }
        ]
    }
    downloads = helper.get_cloud_downloads()

    assert downloads == [
        {
            "name": "video.mkv",
            "torrent_id": "torrent-1",
            "file_id": "file-2",
            "info_hash": "",
            "created_at": "",
            "updated_at": "",
        }
    ]


def test_torbox_helper_get_link_uses_cloud_ids_when_present():
    helper = TorboxHelper()
    helper.client = MagicMock()
    helper.client.create_download_link.return_value = {"data": "https://download"}

    with patch("lib.clients.debrid.torbox.get_public_ip", return_value="127.0.0.1"):
        data = helper.get_link(
            "",
            {"torrent_id": "torrent-1", "file_id": "file-2", "title": "video.mkv"},
        )

    assert data is not None
    assert data["url"] == "https://download"
    helper.client.create_download_link.assert_called_once_with(
        "torrent-1", "file-2", "127.0.0.1"
    )


def test_get_tb_downloads_builds_playable_cloud_entries():
    with patch.object(
        debrid_navigation.TorboxHelper,
        "get_cloud_downloads",
        return_value=[
            {
                "name": "older.mkv",
                "torrent_id": "torrent-1",
                "file_id": "file-1",
                "info_hash": "oldhash",
                "created_at": "2026-03-22T10:00:00Z",
                "updated_at": "2026-03-22T10:00:00Z",
            },
            {
                "name": "video.mkv",
                "torrent_id": "torrent-2",
                "file_id": "file-2",
                "info_hash": "abc123",
                "created_at": "2026-03-23T10:00:00Z",
                "updated_at": "2026-03-23T10:00:00Z",
            },
        ],
    ), patch.object(debrid_navigation.cache, "get", return_value=None), patch.object(
        debrid_navigation.cache, "set"
    ), patch.object(debrid_navigation, "addDirectoryItem") as add_directory_item, patch.object(
        debrid_navigation, "end_of_directory"
    ) as end_of_directory:
        debrid_navigation.get_tb_downloads({})

    assert add_directory_item.call_count == 2
    first_url = add_directory_item.call_args_list[0].args[1]
    second_url = add_directory_item.call_args_list[1].args[1]
    assert "action=play_media" in first_url
    assert "mode%22%3A+%22movie%22" in first_url
    assert "torrent-2" in first_url
    assert "torrent-1" in second_url
    end_of_directory.assert_called_once()
