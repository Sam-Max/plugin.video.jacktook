import json
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest


# Ensure Kodi modules are mocked before importing lib modules
sys.modules.setdefault("xbmc", MagicMock())
sys.modules.setdefault("xbmcgui", MagicMock())
sys.modules.setdefault("xbmcplugin", MagicMock())
sys.modules.setdefault("xbmcvfs", MagicMock())
sys.modules.setdefault("xbmcaddon", MagicMock())


from lib.download_manager import DownloadManager


def _load_downloader_module():
    import importlib

    if "lib.downloader" in sys.modules:
        return importlib.reload(sys.modules["lib.downloader"])
    return importlib.import_module("lib.downloader")


class TestDownloadCloudFile:
    def setup_method(self):
        DownloadManager().clear()

    def test_download_cloud_file_rd_registers_and_starts(self):
        downloader = _load_downloader_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(downloader, "get_setting", side_effect=lambda key, default="": {
                "download_dir": tmpdir,
                "organize_downloads": False,
            }.get(key, default)), patch.object(
                downloader, "translatePath", return_value=tmpdir
            ), patch.object(
                downloader, "normalize_file_name", return_value="Movie.mkv"
            ), patch.object(
                downloader, "Downloader"
            ) as mock_downloader_cls:
                mock_downloader = MagicMock()
                mock_downloader_cls.return_value = mock_downloader

                downloader.download_cloud_file({
                    "url": "https://example.com/Movie.mkv",
                    "filename": "Movie.mkv",
                    "mode": "movie",
                    "debrid_type": "RD",
                })

                manager = DownloadManager()
                entries = manager.list_entries()
                assert len(entries) == 1
                assert entries[0].name == "Movie.mkv"
                assert entries[0].status == "downloading"
                assert entries[0].url == "https://example.com/Movie.mkv"
                assert entries[0].thread is not None

                mock_downloader_cls.assert_called_once()
                call_kwargs = mock_downloader_cls.call_args.kwargs
                assert call_kwargs["url"] == "https://example.com/Movie.mkv"
                assert call_kwargs["name"] == "Movie.mkv"
                assert call_kwargs["destination"] == tmpdir
                assert call_kwargs["registry_id"] is not None
                mock_downloader.run.assert_called_once()

    def test_download_cloud_file_tb_resolves_link_and_starts(self):
        downloader = _load_downloader_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(downloader, "get_setting", side_effect=lambda key, default="": {
                "download_dir": tmpdir,
                "organize_downloads": False,
            }.get(key, default)), patch.object(
                downloader, "translatePath", return_value=tmpdir
            ), patch.object(
                downloader, "normalize_file_name", return_value="Movie.mkv"
            ), patch.object(
                downloader, "Downloader"
            ) as mock_downloader_cls, patch.object(
                downloader, "resolve_cloud_download_url", return_value="https://tb.example.com/Movie.mkv"
            ) as mock_resolve:
                mock_downloader = MagicMock()
                mock_downloader_cls.return_value = mock_downloader

                downloader.download_cloud_file({
                    "torrent_id": "123",
                    "file_id": "456",
                    "filename": "Movie.mkv",
                    "mode": "movie",
                    "debrid_type": "TB",
                })

                mock_resolve.assert_called_once()
                manager = DownloadManager()
                entries = manager.list_entries()
                assert len(entries) == 1
                assert entries[0].url == "https://tb.example.com/Movie.mkv"
                assert entries[0].thread is not None

                call_kwargs = mock_downloader_cls.call_args.kwargs
                assert call_kwargs["destination"] == tmpdir
                mock_downloader.run.assert_called_once()

    def test_download_cloud_file_missing_url_notifies(self):
        downloader = _load_downloader_module()

        with patch.object(downloader, "notification") as mock_notification:
            downloader.download_cloud_file({
                "filename": "Movie.mkv",
                "mode": "movie",
                "debrid_type": "RD",
            })

            mock_notification.assert_called_once()
            manager = DownloadManager()
            assert len(manager.list_entries()) == 0

    def test_download_cloud_file_duplicate_reuses_existing(self):
        downloader = _load_downloader_module()

        manager = DownloadManager()

        with tempfile.TemporaryDirectory() as tmpdir:
            manager.register(name="Movie.mkv", dest_path=os.path.join(tmpdir, "Movie.mkv"), url="https://example.com/Movie.mkv")

            with patch.object(downloader, "get_setting", side_effect=lambda key, default="": {
                "download_dir": tmpdir,
                "organize_downloads": False,
            }.get(key, default)), patch.object(
                downloader, "translatePath", return_value=tmpdir
            ), patch.object(
                downloader, "normalize_file_name", return_value="Movie.mkv"
            ), patch.object(downloader, "notification") as mock_notification:
                downloader.download_cloud_file({
                    "url": "https://example.com/Movie.mkv",
                    "filename": "Movie.mkv",
                    "mode": "movie",
                    "debrid_type": "RD",
                })

                mock_notification.assert_called_once()
                assert len(manager.list_entries()) == 1

    def test_download_cloud_file_uses_organized_destination(self):
        downloader = _load_downloader_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            movies_dir = os.path.join(tmpdir, "Movies")
            with patch.object(downloader, "get_setting", side_effect=lambda key, default="": {
                "download_dir": tmpdir,
                "organize_downloads": True,
                "download_folder_movies": "Movies",
                "download_folder_tvshows": "TV Shows",
            }.get(key, default)), patch.object(
                downloader, "translatePath", return_value=tmpdir
            ), patch.object(
                downloader, "normalize_file_name", return_value="Movie.mkv"
            ), patch.object(
                downloader, "Downloader"
            ) as mock_downloader_cls, patch.object(
                downloader.xbmcvfs, "mkdirs"
            ) as mock_mkdirs:
                mock_downloader = MagicMock()
                mock_downloader_cls.return_value = mock_downloader

                downloader.download_cloud_file({
                    "url": "https://example.com/Movie.mkv",
                    "filename": "Movie.mkv",
                    "mode": "movie",
                    "debrid_type": "RD",
                })

                mock_mkdirs.assert_called_once_with(movies_dir)
                call_kwargs = mock_downloader_cls.call_args.kwargs
                assert call_kwargs["destination"] == movies_dir
                assert call_kwargs["registry_id"] == os.path.join(movies_dir, "Movie.mkv")

    def test_get_rd_downloads_adds_menu_even_without_url(self):
        debrid = __import__("lib.nav.debrid", fromlist=["get_rd_downloads"])

        mock_li = MagicMock()
        with patch.object(debrid, "build_list_item", return_value=mock_li), patch.object(
            debrid, "get_random_color", return_value="red"
        ), patch.object(
            debrid, "get_setting", side_effect=lambda key, default="": "" if key == "real_debrid_token" else default
        ), patch.object(
            debrid.cache, "get", return_value=[{"filename": "Movie.mkv", "download": ""}]
        ), patch.object(
            debrid, "addDirectoryItem"
        ), patch.object(
            debrid, "end_of_directory"
        ), patch.object(
            debrid, "apply_section_view"
        ), patch.object(
            debrid, "action_url_run", return_value="run:download"
        ) as mock_action:
            debrid.get_rd_downloads({"page": 1})
            mock_li.addContextMenuItems.assert_called_once()
            assert mock_action.call_count == 1
            assert mock_action.call_args.kwargs.get("url") == ""

    def test_resolve_cloud_download_url_rd_returns_direct(self):
        debrid = __import__("lib.nav.debrid", fromlist=["resolve_cloud_download_url"])

        result = debrid.resolve_cloud_download_url({
            "debrid_type": "RD",
            "url": "https://example.com/Movie.mkv",
        })
        assert result == "https://example.com/Movie.mkv"

    def test_resolve_cloud_download_url_rd_missing_url_returns_none(self):
        debrid = __import__("lib.nav.debrid", fromlist=["resolve_cloud_download_url"])

        result = debrid.resolve_cloud_download_url({
            "debrid_type": "RD",
        })
        assert result is None

    def test_resolve_cloud_download_url_tb_calls_create_link(self):
        debrid = __import__("lib.nav.debrid", fromlist=["resolve_cloud_download_url"])

        mock_client = MagicMock()
        mock_client.create_download_link.return_value = {
            "data": "https://tb.example.com/Movie.mkv"
        }
        mock_helper = MagicMock()
        mock_helper.client = mock_client

        with patch.object(debrid, "TorboxHelper", return_value=mock_helper), patch.object(
            debrid, "get_public_ip", return_value="1.2.3.4"
        ), patch.object(debrid.cache, "get", return_value=None), patch.object(
            debrid.cache, "set"
        ):
            result = debrid.resolve_cloud_download_url({
                "debrid_type": "TB",
                "torrent_id": "123",
                "file_id": "456",
            })

        assert result == "https://tb.example.com/Movie.mkv"
        mock_client.create_download_link.assert_called_once_with("123", "456", "1.2.3.4")

    def test_resolve_cloud_download_url_tb_failure_returns_none(self):
        debrid = __import__("lib.nav.debrid", fromlist=["resolve_cloud_download_url"])

        mock_client = MagicMock()
        mock_client.create_download_link.return_value = None
        mock_helper = MagicMock()
        mock_helper.client = mock_client

        with patch.object(debrid, "TorboxHelper", return_value=mock_helper), patch.object(
            debrid, "get_public_ip", return_value="1.2.3.4"
        ), patch.object(debrid.cache, "get", return_value=None), patch.object(
            debrid.cache, "set"
        ):
            result = debrid.resolve_cloud_download_url({
                "debrid_type": "TB",
                "torrent_id": "123",
                "file_id": "456",
            })

        assert result is None

    def test_resolve_cloud_download_url_tb_caches_result(self):
        debrid = __import__("lib.nav.debrid", fromlist=["resolve_cloud_download_url"])

        mock_client = MagicMock()
        mock_client.create_download_link.return_value = {
            "data": "https://tb.example.com/Movie.mkv"
        }
        mock_helper = MagicMock()
        mock_helper.client = mock_client

        with patch.object(debrid, "TorboxHelper", return_value=mock_helper), patch.object(
            debrid, "get_public_ip", return_value="1.2.3.4"
        ), patch.object(debrid.cache, "get", side_effect=[None, "https://tb.example.com/Movie.mkv"]) as mock_cache_get, patch.object(
            debrid.cache, "set"
        ) as mock_cache_set:
            result1 = debrid.resolve_cloud_download_url({
                "debrid_type": "TB",
                "torrent_id": "123",
                "file_id": "456",
            })
            assert result1 == "https://tb.example.com/Movie.mkv"
            mock_client.create_download_link.assert_called_once_with("123", "456", "1.2.3.4")
            mock_cache_set.assert_called_once()

            result2 = debrid.resolve_cloud_download_url({
                "debrid_type": "TB",
                "torrent_id": "123",
                "file_id": "456",
            })
            assert result2 == "https://tb.example.com/Movie.mkv"
            assert mock_client.create_download_link.call_count == 1
