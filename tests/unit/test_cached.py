"""Unit tests for the cache layer (MemoryCache and SQLiteCache)."""

import sqlite3
import threading
from datetime import timedelta
from hashlib import sha256

import pytest

from lib.db.cached import MemoryCache, SQLiteCache, pickle_hash

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeWindow:
    """Dict-backed stand-in for xbmcgui.Window(10000)."""

    def __init__(self):
        self._props = {}

    def getProperty(self, key):
        return self._props.get(key, "")

    def setProperty(self, key, value):
        self._props[key] = value

    def clearProperty(self, key):
        self._props.pop(key, None)


@pytest.fixture
def memory_cache():
    cache = MemoryCache(database="testdb")
    cache._window = FakeWindow()
    return cache


@pytest.fixture
def sqlite_cache(tmp_path, monkeypatch):
    """SQLiteCache backed by a real sqlite file on disk.

    tests/conftest.py replaces sqlite3.connect with a MagicMock globally;
    restore the real implementation for these tests only.
    """
    monkeypatch.setattr(sqlite3, "connect", sqlite3.dbapi2.connect)
    db_path = str(tmp_path / "test_cache.sqlite")
    cache = SQLiteCache(database=db_path)
    yield cache
    cache.close()


class LockRecorder:
    """Lock-like object that records how many times it was entered."""

    def __init__(self):
        self._lock = threading.Lock()
        self.acquired = 0

    def __enter__(self):
        with self._lock:
            self.acquired += 1
        return self

    def __exit__(self, *args):
        return False


# ---------------------------------------------------------------------------
# Key generation
# ---------------------------------------------------------------------------


class TestKeyGeneration:
    def test_pickle_hash_is_sha256_of_pickle(self):
        obj = {"a": 1}
        expected = sha256(__import__("pickle").dumps(obj)).hexdigest()
        assert pickle_hash(obj) == expected

    def test_generate_key_hashes_by_default(self, memory_cache):
        key = memory_cache._generate_key("foo")
        assert key == pickle_hash("foo")

    def test_generate_key_hashed_shortcut(self, memory_cache):
        assert memory_cache._generate_key("raw-key", hashed_key=True) == "raw-key"

    def test_generate_key_appends_identifier(self, memory_cache):
        key = memory_cache._generate_key("foo", identifier="::extra")
        assert key == pickle_hash("foo") + "::extra"


# ---------------------------------------------------------------------------
# MemoryCache
# ---------------------------------------------------------------------------


class TestMemoryCache:
    def test_set_and_get_roundtrip(self, memory_cache):
        memory_cache.set("key1", {"data": 123})
        assert memory_cache.get("key1") == {"data": 123}

    def test_missing_key_returns_none(self, memory_cache):
        assert memory_cache.get("nope") is None

    def test_expired_entry_returns_none_and_is_deleted(self, memory_cache):
        memory_cache.set("key1", "value", expires=timedelta(seconds=-1))
        assert memory_cache.get("key1") is None
        # The property and the key index entry must be gone.
        assert memory_cache._window.getProperty(memory_cache._database + "key1") == ""
        assert "key1" not in memory_cache._get_key_index()

    def test_zero_expiry_does_not_store(self, memory_cache):
        memory_cache._set("key1", "value", timedelta(0))
        assert memory_cache.get("key1") is None

    def test_delete_removes_key_and_index_entry(self, memory_cache):
        memory_cache.set("key1", "value")
        memory_cache.delete("key1")
        assert memory_cache.get("key1") is None
        assert "key1" not in memory_cache._get_key_index()

    def test_delete_like_removes_matching_keys_only(self, memory_cache):
        memory_cache.set("user:1", "a")
        memory_cache.set("user:2", "b")
        memory_cache.set("other:3", "c")
        memory_cache.delete_like("user:%")
        assert memory_cache.get("user:1") is None
        assert memory_cache.get("user:2") is None
        assert memory_cache.get("other:3") == "c"

    def test_clean_all_clears_everything(self, memory_cache):
        memory_cache.set("a", 1)
        memory_cache.set("b", 2)
        memory_cache.clean_all()
        assert memory_cache.get("a") is None
        assert memory_cache.get("b") is None


# ---------------------------------------------------------------------------
# SQLiteCache
# ---------------------------------------------------------------------------


class TestSQLiteCache:
    def test_set_and_get_roundtrip(self, sqlite_cache):
        sqlite_cache.set("key1", {"data": 42}, timedelta(hours=1))
        assert sqlite_cache.get("key1") == {"data": 42}

    def test_missing_key_returns_none(self, sqlite_cache):
        assert sqlite_cache.get("nope") is None

    def test_expired_key_returns_none(self, sqlite_cache):
        sqlite_cache.set("key1", "value", timedelta(seconds=-1))
        assert sqlite_cache.get("key1") is None

    def test_delete_removes_key(self, sqlite_cache):
        sqlite_cache.set("key1", "value", timedelta(hours=1))
        sqlite_cache.delete("key1")
        assert sqlite_cache.get("key1") is None

    def test_delete_like_removes_matching_keys_only(self, sqlite_cache):
        sqlite_cache.set("user:1", "a", timedelta(hours=1))
        sqlite_cache.set("user:2", "b", timedelta(hours=1))
        sqlite_cache.set("other:3", "c", timedelta(hours=1))
        sqlite_cache.delete_like("user:%")
        assert sqlite_cache.get("user:1") is None
        assert sqlite_cache.get("user:2") is None
        assert sqlite_cache.get("other:3") == "c"

    def test_clean_up_removes_expired_rows(self, sqlite_cache):
        sqlite_cache.set("expired", "old", timedelta(seconds=-1))
        sqlite_cache.set("fresh", "new", timedelta(hours=1))
        sqlite_cache.clean_up()
        assert sqlite_cache.get("expired") is None
        assert sqlite_cache.get("fresh") == "new"

    def test_check_clean_up_triggers_after_interval(self, sqlite_cache):
        sqlite_cache._cleanup_interval = timedelta(seconds=0)
        sqlite_cache._last_cleanup = sqlite_cache._last_cleanup - timedelta(minutes=1)
        assert sqlite_cache.check_clean_up() is True

    def test_clean_all_clears_rows_and_object_store(self, sqlite_cache):
        sqlite_cache.set("key1", "value", timedelta(hours=1))
        sqlite_cache._object_store["raw"] = ("x", None)
        sqlite_cache.clean_all()
        assert sqlite_cache.get("key1") is None
        assert sqlite_cache._object_store == {}

    def test_fallback_to_object_store_on_sql_error(self, sqlite_cache, monkeypatch):
        def broken_check():
            raise RuntimeError("db gone")

        monkeypatch.setattr(sqlite_cache, "check_clean_up", broken_check)
        sqlite_cache.set("key1", "fallback", timedelta(hours=1))
        assert sqlite_cache._object_store["key1"][0] == "fallback"
        # The fallback entry must store an absolute expiry so get() can compare it.
        assert sqlite_cache.get("key1") == "fallback"

    def test_delete_and_delete_like_remove_fallback_entries(self, sqlite_cache, monkeypatch):
        real_check_clean_up = sqlite_cache.check_clean_up

        def broken_check():
            raise RuntimeError("db gone")

        # Force the object-store fallback while writing.
        monkeypatch.setattr(sqlite_cache, "check_clean_up", broken_check)
        sqlite_cache.set("user:1", "fallback-a", timedelta(hours=1))
        sqlite_cache.set("other:3", "fallback-c", timedelta(hours=1))
        assert sqlite_cache.get("user:1") == "fallback-a"
        assert sqlite_cache.get("other:3") == "fallback-c"

        monkeypatch.setattr(sqlite_cache, "check_clean_up", real_check_clean_up)

        sqlite_cache.delete("user:1")
        assert sqlite_cache.get("user:1") is None

        sqlite_cache.delete_like("other:%")
        assert sqlite_cache.get("other:3") is None

    def test_delete_and_delete_like_use_lock(self, sqlite_cache):
        recorder = LockRecorder()
        sqlite_cache._lock = recorder
        sqlite_cache.delete("key1")
        sqlite_cache.delete_like("key%")
        assert recorder.acquired == 2

    def test_concurrent_operations_do_not_error(self, sqlite_cache):
        errors = []

        def worker(i):
            try:
                for j in range(10):
                    key = f"k:{i}:{j}"
                    sqlite_cache.set(key, j, timedelta(hours=1))
                    assert sqlite_cache.get(key) == j
                    sqlite_cache.delete(key)
                    assert sqlite_cache.get(key) is None
            except Exception as exc:  # pragma: no cover - collected below
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,), daemon=True) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        for t in threads:
            assert not t.is_alive(), f"{t.name} did not finish (deadlock?)"
        assert errors == []

    def test_cleanup_from_get_and_set_does_not_deadlock(self, tmp_path, monkeypatch):
        """Regression: cleanup fired inside get()/set() must not self-deadlock.

        ``cleanup_interval=timedelta(0)`` forces ``check_clean_up()`` to fire
        on the first ``get()``/``set()`` while ``self._lock`` is already held.
        """
        monkeypatch.setattr(sqlite3, "connect", sqlite3.dbapi2.connect)
        cache = SQLiteCache(
            database=str(tmp_path / "deadlock.sqlite"),
            cleanup_interval=timedelta(0),
        )
        cache._last_cleanup = cache._last_cleanup - timedelta(minutes=1)
        try:
            errors = []

            def worker():
                try:
                    cache.set("k", "v", timedelta(hours=1))
                    assert cache.get("k") == "v"
                except Exception as exc:  # pragma: no cover - collected below
                    errors.append(exc)

            thread = threading.Thread(target=worker, daemon=True)
            thread.start()
            thread.join(timeout=5)
            assert not thread.is_alive(), "cache get/set deadlocked inside check_clean_up()"
            assert errors == []
        finally:
            cache.close()


# ---------------------------------------------------------------------------
# Persistence across instances
# ---------------------------------------------------------------------------


class TestSQLiteCachePersistence:
    def test_data_survives_reconnect(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sqlite3, "connect", sqlite3.dbapi2.connect)
        db_path = str(tmp_path / "persist.sqlite")

        cache1 = SQLiteCache(database=db_path)
        cache1.set("durable", {"n": 7}, timedelta(hours=1))
        cache1.close()

        cache2 = SQLiteCache(database=db_path)
        assert cache2.get("durable") == {"n": 7}
        cache2.close()
