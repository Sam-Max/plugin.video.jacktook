import threading
import time
from unittest.mock import MagicMock

import pytest

from lib.download_manager import DownloadManager, DownloadEntry


class TestDownloadManager:
    def setup_method(self):
        DownloadManager().clear()

    def test_register_creates_entry(self):
        manager = DownloadManager()
        entry = manager.register(
            name="test.mp4",
            dest_path="/downloads/test.mp4",
            url="https://example.com/test.mp4",
        )

        assert entry.name == "test.mp4"
        assert entry.dest_path == "/downloads/test.mp4"
        assert entry.url == "https://example.com/test.mp4"
        assert entry.status == "downloading"
        assert entry.progress == 0
        assert entry.id == "/downloads/test.mp4"

    def test_register_duplicate_rejects_second_download(self):
        manager = DownloadManager()
        manager.register(
            name="test.mp4",
            dest_path="/downloads/test.mp4",
            url="https://example.com/test.mp4",
        )

        result = manager.register(
            name="test.mp4",
            dest_path="/downloads/test.mp4",
            url="https://example.com/test.mp4",
        )

        assert result is None
        assert len(manager.registry) == 1

    def test_register_duplicate_allows_after_completed(self):
        manager = DownloadManager()
        manager.register(
            name="test.mp4",
            dest_path="/downloads/test.mp4",
            url="https://example.com/test.mp4",
        )
        manager.set_status("/downloads/test.mp4", "completed")

        result = manager.register(
            name="test.mp4",
            dest_path="/downloads/test.mp4",
            url="https://example.com/test.mp4",
        )

        assert result is not None
        assert result.status == "downloading"

    def test_update_progress_updates_fields(self):
        manager = DownloadManager()
        manager.register(
            name="test.mp4",
            dest_path="/downloads/test.mp4",
            url="https://example.com/test.mp4",
        )

        manager.update_progress(
            "/downloads/test.mp4",
            downloaded=5_000_000,
            speed=1_000_000,
            eta=60,
            progress=50,
            size=10_000_000,
        )

        entry = manager.get_entry("/downloads/test.mp4")
        assert entry.downloaded == 5_000_000
        assert entry.speed == 1_000_000
        assert entry.eta == 60
        assert entry.progress == 50
        assert entry.size == 10_000_000

    def test_set_status_changes_status(self):
        manager = DownloadManager()
        manager.register(
            name="test.mp4",
            dest_path="/downloads/test.mp4",
            url="https://example.com/test.mp4",
        )

        manager.set_status("/downloads/test.mp4", "paused")
        entry = manager.get_entry("/downloads/test.mp4")
        assert entry.status == "paused"

    def test_get_entry_missing_returns_none(self):
        manager = DownloadManager()
        assert manager.get_entry("/downloads/missing.mp4") is None

    def test_remove_entry_deletes_from_registry(self):
        manager = DownloadManager()
        manager.register(
            name="test.mp4",
            dest_path="/downloads/test.mp4",
            url="https://example.com/test.mp4",
        )

        manager.remove_entry("/downloads/test.mp4")
        assert manager.get_entry("/downloads/test.mp4") is None

    def test_list_entries_returns_all(self):
        manager = DownloadManager()
        manager.register(name="a.mp4", dest_path="/downloads/a.mp4", url="https://example.com/a.mp4")
        manager.register(name="b.mp4", dest_path="/downloads/b.mp4", url="https://example.com/b.mp4")

        entries = manager.list_entries()
        assert len(entries) == 2
        assert {e.name for e in entries} == {"a.mp4", "b.mp4"}

    def test_singleton_same_instance(self):
        manager1 = DownloadManager()
        manager2 = DownloadManager()
        assert manager1 is manager2

    def test_update_progress_missing_entry_no_crash(self):
        manager = DownloadManager()
        manager.update_progress(
            "/downloads/missing.mp4",
            downloaded=1,
            speed=1,
            eta=1,
            progress=1,
            size=1,
        )
        assert manager.get_entry("/downloads/missing.mp4") is None

    def test_set_status_missing_entry_no_crash(self):
        manager = DownloadManager()
        manager.set_status("/downloads/missing.mp4", "paused")
        assert manager.get_entry("/downloads/missing.mp4") is None

    def test_register_with_thread(self):
        manager = DownloadManager()
        mock_thread = MagicMock()
        entry = manager.register(
            name="test.mp4",
            dest_path="/downloads/test.mp4",
            url="https://example.com/test.mp4",
            thread=mock_thread,
        )
        assert entry.thread is mock_thread

    def test_clear_removes_all_entries(self):
        manager = DownloadManager()
        manager.register(name="a.mp4", dest_path="/downloads/a.mp4", url="https://example.com/a.mp4")
        manager.clear()
        assert manager.list_entries() == []

    def test_concurrent_register_no_exceptions(self):
        manager = DownloadManager()
        errors = []

        def worker(i):
            try:
                manager.register(
                    name=f"file{i}.mp4",
                    dest_path=f"/downloads/file{i}.mp4",
                    url=f"https://example.com/file{i}.mp4",
                )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(manager.registry) == 20

    def test_concurrent_update_no_exceptions(self):
        manager = DownloadManager()
        manager.register(
            name="test.mp4",
            dest_path="/downloads/test.mp4",
            url="https://example.com/test.mp4",
        )
        errors = []

        def worker(i):
            try:
                manager.update_progress(
                    "/downloads/test.mp4",
                    downloaded=i * 1_000_000,
                    speed=1_000_000,
                    eta=60,
                    progress=i * 5,
                    size=20_000_000,
                )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        entry = manager.get_entry("/downloads/test.mp4")
        assert entry is not None
