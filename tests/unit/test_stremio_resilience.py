from unittest.mock import MagicMock

from lib import search
from lib.api.stremio.addon_manager import AddonManager
from lib.clients.subtitle import opensubstremio


def _addon_item(manifest):
    return {"manifest": manifest, "transportUrl": "https://example.com/config/manifest.json"}


def test_malformed_addon_isolated_without_logging_manifest_data(monkeypatch):
    logs = []
    monkeypatch.setattr("lib.api.stremio.addon_manager.kodilog", logs.append)
    manager = AddonManager([{"manifest": "not-an-object", "transportUrl": "https://invalid.example/value"}, _addon_item({"id": "valid.addon", "name": "Valid", "types": ["movie"], "resources": ["stream"]})])

    assert [addon.manifest.id for addon in manager.addons] == ["valid.addon"]
    assert logs == ["Skipped malformed Stremio addon entry at index 0"]
    assert "invalid.example" not in logs[0]


def test_tmdb_only_ids_schedule_stremio_in_both_schedulers(monkeypatch):
    manager = AddonManager([_addon_item({"id": "tmdb.addon", "name": "TMDB", "types": ["movie"], "resources": [{"name": "stream", "types": ["movie"], "idPrefixes": ["tmdb"]}]})])
    addon = manager.addons[0]
    monkeypatch.setattr(search, "get_setting", lambda key, default=None: key == "stremio_enabled")
    monkeypatch.setattr(search, "get_selected_stream_addons", lambda: [addon])
    monkeypatch.setattr(search, "_is_source_enabled", lambda *_args: True)
    monkeypatch.setattr(search, "get_addon_display_name", lambda item: item.manifest.name)

    class Executor:
        def __init__(self): self.calls = []
        def submit(self, *args, **kwargs):
            self.calls.append((args, kwargs))
            return MagicMock()

    class Manager:
        def __init__(self): self.calls = []
        def submit_task(self, *args, **kwargs): self.calls.append((args, kwargs))

    executor = Executor()
    tasks = []
    search._submit_search_tasks(executor, tasks, None, "Title", "movies", "movies", None, None, {"tmdb_id": "42"}, "", "42", "", False)
    managed = Manager()
    search._submit_search_tasks_managed(managed, None, "Title", "movies", "movies", None, None, {"tmdb_id": "42"}, "", "42", "")

    assert sum(call[0][1] == search.Indexer.STREMIO for call in executor.calls) == 1
    assert sum(call[0][1] == search.Indexer.STREMIO for call in managed.calls) == 1


def test_worker_bounds_are_conservative(monkeypatch):
    monkeypatch.setattr(search, "get_setting", lambda *_args: 999)
    assert search._search_worker_count() == search.MAX_SEARCH_WORKERS
    assert opensubstremio.MAX_SUBTITLE_WORKERS <= search.MAX_SEARCH_WORKERS
