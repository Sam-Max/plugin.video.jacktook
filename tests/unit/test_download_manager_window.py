import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from lib.download_manager import DownloadManager
from lib.gui.download_manager_window import DownloadManagerWindow


class TestDownloadManagerWindow:
    def setup_method(self):
        DownloadManager().clear()

    def test_on_init_sets_empty_message_when_no_entries(self):
        window = DownloadManagerWindow("download_manager.xml", "")
        window.setProperty = MagicMock()
        window.getControl = MagicMock(return_value=MagicMock())

        window.onInit()

        window.setProperty.assert_any_call("downloads_empty", "true")
        assert isinstance(window._poll_thread, threading.Thread)

    def test_on_init_starts_polling_thread(self):
        window = DownloadManagerWindow("download_manager.xml", "")
        window.setProperty = MagicMock()
        window.getControl = MagicMock(return_value=MagicMock())
        window._monitor = MagicMock()
        window._monitor.abortRequested.return_value = False

        with patch("lib.gui.download_manager_window.xbmc.sleep") as mock_sleep:
            call_count = [0]

            def sleep_side_effect(ms):
                call_count[0] += 1
                if call_count[0] >= 1:
                    window._closed = True

            mock_sleep.side_effect = sleep_side_effect
            window.onInit()
            window._poll_thread.join(timeout=1)

        assert call_count[0] >= 1

    def test_rebuild_list_sets_empty_when_no_entries(self):
        window = DownloadManagerWindow("download_manager.xml", "")
        window.setProperty = MagicMock()
        mock_list = MagicMock()
        window.getControl = MagicMock(return_value=mock_list)

        window._rebuild_list()

        window.setProperty.assert_any_call("downloads_empty", "true")
        mock_list.reset.assert_called_once()

    def test_rebuild_list_adds_items_for_entries(self):
        manager = DownloadManager()
        manager.register(name="a.mkv", dest_path="/dl/a.mkv", url="https://example.com/a.mkv")
        manager.register(name="b.mkv", dest_path="/dl/b.mkv", url="https://example.com/b.mkv")

        window = DownloadManagerWindow("download_manager.xml", "")
        window.setProperty = MagicMock()
        mock_list = MagicMock()
        window.getControl = MagicMock(return_value=mock_list)

        window._rebuild_list()

        assert mock_list.addItem.call_count == 2
        window.setProperty.assert_any_call("downloads_empty", "false")

    def test_rebuild_list_preserves_focus_position(self):
        manager = DownloadManager()
        manager.register(name="a.mkv", dest_path="/dl/a.mkv", url="https://example.com/a.mkv")
        manager.register(name="b.mkv", dest_path="/dl/b.mkv", url="https://example.com/b.mkv")

        window = DownloadManagerWindow("download_manager.xml", "")
        window.setProperty = MagicMock()
        mock_list = MagicMock()
        mock_list.getSelectedPosition.return_value = 1
        mock_list.size.return_value = 2
        window.getControl = MagicMock(return_value=mock_list)

        window._rebuild_list()

        mock_list.reset.assert_called_once()
        assert mock_list.addItem.call_count == 2
        mock_list.selectItem.assert_called_once_with(1)

    def test_rebuild_list_does_not_select_out_of_range(self):
        manager = DownloadManager()
        manager.register(name="a.mkv", dest_path="/dl/a.mkv", url="https://example.com/a.mkv")

        window = DownloadManagerWindow("download_manager.xml", "")
        window.setProperty = MagicMock()
        mock_list = MagicMock()
        mock_list.getSelectedPosition.return_value = 5
        mock_list.size.return_value = 1
        window.getControl = MagicMock(return_value=mock_list)

        window._rebuild_list()

        mock_list.selectItem.assert_not_called()

    def test_on_click_pause_sets_cancel_flag(self):
        manager = DownloadManager()
        manager.register(name="a.mkv", dest_path="/dl/a.mkv", url="https://example.com/a.mkv")

        window = DownloadManagerWindow("download_manager.xml", "")
        mock_list = MagicMock()
        mock_list.getSelectedItem.return_value.getProperty.return_value = "/dl/a.mkv"
        window.getControl = MagicMock(return_value=mock_list)
        window._rebuild_list = MagicMock()

        window.onClick(14003)  # Pause

        entry = manager.get_entry("/dl/a.mkv")
        assert entry.cancel_flag is True

    def test_on_click_pause_passes_refresh_false(self):
        manager = DownloadManager()
        manager.register(name="a.mkv", dest_path="/dl/a.mkv", url="https://example.com/a.mkv")

        window = DownloadManagerWindow("download_manager.xml", "")
        mock_list = MagicMock()
        mock_list.getSelectedItem.return_value.getProperty.return_value = "/dl/a.mkv"
        window.getControl = MagicMock(return_value=mock_list)
        window._rebuild_list = MagicMock()

        with patch("lib.gui.download_manager_window.handle_pause_download") as mock_handle_pause:
            window.onClick(14003)  # Pause
            mock_handle_pause.assert_called_once()
            assert mock_handle_pause.call_args.kwargs.get("refresh") is False

    def test_on_click_resume_starts_download(self):
        manager = DownloadManager()
        manager.register(name="a.mkv", dest_path="/dl/a.mkv", url="https://example.com/a.mkv")
        manager.set_status("/dl/a.mkv", "paused")

        window = DownloadManagerWindow("download_manager.xml", "")
        mock_list = MagicMock()
        mock_list.getSelectedItem.return_value.getProperty.return_value = "/dl/a.mkv"
        window.getControl = MagicMock(return_value=mock_list)
        window._rebuild_list = MagicMock()

        with patch("lib.gui.download_manager_window.Downloader") as mock_dl:
            window.onClick(14004)  # Resume
            mock_dl.assert_called_once()
            mock_dl.return_value.run.assert_called_once()

    def test_on_click_cancel_sets_status_cancelled(self):
        manager = DownloadManager()
        manager.register(name="a.mkv", dest_path="/dl/a.mkv", url="https://example.com/a.mkv")

        window = DownloadManagerWindow("download_manager.xml", "")
        mock_list = MagicMock()
        mock_list.getSelectedItem.return_value.getProperty.return_value = "/dl/a.mkv"
        window.getControl = MagicMock(return_value=mock_list)
        window._rebuild_list = MagicMock()

        window.onClick(14005)  # Cancel

        entry = manager.get_entry("/dl/a.mkv")
        assert entry.status == "cancelled"

    def test_on_click_delete_removes_entry(self):
        manager = DownloadManager()
        manager.register(name="a.mkv", dest_path="/dl/a.mkv", url="https://example.com/a.mkv")

        window = DownloadManagerWindow("download_manager.xml", "")
        mock_list = MagicMock()
        mock_list.getSelectedItem.return_value.getProperty.return_value = "/dl/a.mkv"
        window.getControl = MagicMock(return_value=mock_list)
        window._rebuild_list = MagicMock()

        with patch("lib.gui.download_manager_window.xbmcvfs") as mock_vfs:
            window.onClick(14006)  # Delete
            assert manager.get_entry("/dl/a.mkv") is None

    def test_on_click_clear_completed_removes_only_completed(self):
        manager = DownloadManager()
        manager.register(name="a.mkv", dest_path="/dl/a.mkv", url="https://example.com/a.mkv")
        manager.register(name="b.mkv", dest_path="/dl/b.mkv", url="https://example.com/b.mkv")
        manager.set_status("/dl/b.mkv", "completed")

        window = DownloadManagerWindow("download_manager.xml", "")
        window._rebuild_list = MagicMock()

        window.onClick(14007)  # Clear Completed

        assert manager.get_entry("/dl/a.mkv") is not None
        assert manager.get_entry("/dl/b.mkv") is None

    def test_poll_loop_updates_selected_properties(self):
        manager = DownloadManager()
        manager.register(name="a.mkv", dest_path="/dl/a.mkv", url="https://example.com/a.mkv")
        manager.update_progress("/dl/a.mkv", downloaded=50, speed=1000, eta=60, progress=50, size=100)

        window = DownloadManagerWindow("download_manager.xml", "")
        window.setProperty = MagicMock()
        mock_selected_item = MagicMock()
        mock_selected_item.getProperty.return_value = "/dl/a.mkv"
        mock_list = MagicMock()
        mock_list.getSelectedItem.return_value = mock_selected_item
        window.getControl = MagicMock(return_value=mock_list)
        window._focused_item_id = "/dl/a.mkv"
        window._monitor = MagicMock()
        window._monitor.abortRequested.return_value = False

        with patch("lib.gui.download_manager_window.xbmc.sleep") as mock_sleep:
            call_count = [0]

            def sleep_side_effect(ms):
                call_count[0] += 1
                if call_count[0] >= 1:
                    window._closed = True

            mock_sleep.side_effect = sleep_side_effect
            window._poll_loop()

        window.setProperty.assert_any_call("selected_progress", "50")
        window.setProperty.assert_any_call("selected_speed", "1e+03 B/s")
        window.setProperty.assert_any_call("selected_eta", "1m 0s")
        window.setProperty.assert_any_call("selected_size", "100 B")

    def test_on_action_sets_closed_flag(self):
        window = DownloadManagerWindow("download_manager.xml", "")
        window._closed = False
        mock_action = MagicMock()
        mock_action.getId.return_value = 10  # ACTION_PREVIOUS_MENU

        window.onAction(mock_action)

        assert window._closed is True

    def test_sync_from_disk_registers_existing_downloads(self):
        """_sync_from_disk should register downloads found in .jacktook.json files."""
        DownloadManager().clear()
        window = DownloadManagerWindow("download_manager.xml", "")
        window.setProperty = MagicMock()

        meta = {"title": "Completed Movie", "status": "completed", "progress": 100, "url": "https://example.com/movie.mkv"}
        with patch("lib.gui.download_manager_window.os.path.isdir", return_value=True), \
             patch("lib.gui.download_manager_window.os.listdir", return_value=["movie.mkv.jacktook.json"]), \
             patch("lib.gui.download_manager_window.get_download_metadata", return_value=meta), \
             patch("lib.gui.download_manager_window._get_setting", return_value="/dl"), \
             patch("lib.gui.download_manager_window._translatePath", side_effect=lambda x: x):
            window._sync_from_disk()

        manager = DownloadManager()
        entries = manager.list_entries()
        assert len(entries) == 1
        assert entries[0].status == "completed"
        assert entries[0].progress == 100

    def test_sync_from_disk_skips_cancelled_downloads(self):
        """_sync_from_disk should skip entries with cancelled status."""
        DownloadManager().clear()
        window = DownloadManagerWindow("download_manager.xml", "")
        window.setProperty = MagicMock()

        meta = {"title": "Cancelled File", "status": "cancelled", "progress": 30, "url": "https://example.com/cancel.mkv"}
        with patch("lib.gui.download_manager_window.os.path.isdir", return_value=True), \
             patch("lib.gui.download_manager_window.os.listdir", return_value=["cancel.mkv.jacktook.json"]), \
             patch("lib.gui.download_manager_window.get_download_metadata", return_value=meta), \
             patch("lib.gui.download_manager_window._get_setting", return_value="/dl"), \
             patch("lib.gui.download_manager_window._translatePath", side_effect=lambda x: x):
            window._sync_from_disk()

        manager = DownloadManager()
        assert len(manager.list_entries()) == 0

    def test_sync_from_disk_skips_already_registered(self):
        """_sync_from_disk should not re-register entries already in the registry."""
        DownloadManager().clear()
        download_dir = "/dl"
        manager = DownloadManager()
        # Pre-register an entry at the path that _sync_from_disk would compute
        existing_dest = f"{download_dir}/existing.mkv"
        manager.register(name="Existing", dest_path=existing_dest, url="https://example.com/existing.mkv")

        window = DownloadManagerWindow("download_manager.xml", "")
        window.setProperty = MagicMock()

        meta = {"title": "Existing", "status": "completed", "progress": 100, "url": "https://example.com/existing.mkv"}
        with patch("lib.gui.download_manager_window.os.path.isdir", return_value=True), \
             patch("lib.gui.download_manager_window.os.listdir", return_value=["existing.mkv.jacktook.json"]), \
             patch("lib.gui.download_manager_window.get_download_metadata", return_value=meta), \
             patch("lib.gui.download_manager_window._get_setting", return_value=download_dir), \
             patch("lib.gui.download_manager_window._translatePath", side_effect=lambda x: x):
            window._sync_from_disk()

        # Should still be only 1 entry, not duplicated
        assert len(manager.list_entries()) == 1
