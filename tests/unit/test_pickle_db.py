"""Unit tests for the PickleDatabase persistence layer."""

import os
import pickle

import pytest

import lib.db.pickle_db as pickle_db_mod
from lib.db.pickle_db import PickleDatabase

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeXbmcvfs:
    """Stand-in for xbmcvfs that resolves special:// paths to a tmp dir."""

    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.created_dirs = []

    def translatePath(self, path):
        return self.base_dir

    def mkdirs(self, path):
        os.makedirs(path, exist_ok=True)
        self.created_dirs.append(path)


@pytest.fixture
def data_dir(tmp_path):
    return str(tmp_path / "addon_data")


@pytest.fixture
def db_path(data_dir):
    return os.path.join(data_dir, "database.pickle")


@pytest.fixture
def make_db(tmp_path, data_dir, monkeypatch):
    """Factory for PickleDatabase instances rooted at a temp directory."""

    def _make():
        fake_vfs = FakeXbmcvfs(data_dir)
        monkeypatch.setattr(pickle_db_mod.xbmcvfs, "translatePath", fake_vfs.translatePath)
        monkeypatch.setattr(pickle_db_mod.xbmcvfs, "mkdirs", fake_vfs.mkdirs)
        return PickleDatabase()

    return _make


# ---------------------------------------------------------------------------
# Basic flows
# ---------------------------------------------------------------------------


class TestBasicFlows:
    def test_default_keys_are_seeded(self, make_db):
        db = make_db()
        for key in ("jt:watch", "jt:lth", "jt:lfh", "jt:lib"):
            assert db.get_key(key) == {}

    def test_set_and_get_item(self, make_db):
        db = make_db()
        db.set_item("jt:watch", "tt123", {"progress": 50})
        assert db.get_item("jt:watch", "tt123") == {"progress": 50}

    def test_get_item_missing_subkey_returns_none(self, make_db):
        db = make_db()
        assert db.get_item("jt:watch", "missing") is None

    def test_delete_item_removes_subkey(self, make_db):
        db = make_db()
        db.set_item("jt:watch", "tt123", {"progress": 50})
        db.delete_item("jt:watch", "tt123")
        assert db.get_item("jt:watch", "tt123") is None

    def test_delete_item_missing_key_does_not_raise(self, make_db):
        db = make_db()
        db.delete_item("jt:missing", "tt123")

    def test_set_and_get_key(self, make_db):
        db = make_db()
        db.set_key("jt:lib", {"movies": [1, 2, 3]})
        assert db.get_key("jt:lib") == {"movies": [1, 2, 3]}

    def test_no_commit_leaves_file_untouched(self, make_db, db_path):
        db = make_db()
        db.set_item("jt:watch", "tt123", {"progress": 50}, commit=False)
        assert not os.path.exists(db_path)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_commit_persists_across_instance_reload(self, make_db, db_path):
        db1 = make_db()
        db1.set_item("jt:watch", "tt123", {"progress": 50})
        assert os.path.exists(db_path)

        db2 = make_db()
        assert db2.get_item("jt:watch", "tt123") == {"progress": 50}

    def test_reload_merges_base_keys_with_stored_data(self, make_db):
        db1 = make_db()
        db1.set_item("jt:watch", "tt123", {"progress": 1})

        db2 = make_db()
        # Base keys are present alongside the persisted data.
        assert db2.get_key("jt:lth") == {}
        assert db2.get_item("jt:watch", "tt123") == {"progress": 1}

    def test_corrupt_file_loads_as_empty_database(self, make_db, db_path):
        db1 = make_db()
        db1.set_key("jt:lib", {"a": 1})
        with open(db_path, "wb") as f:
            f.write(b"not a pickle")

        db2 = make_db()
        assert db2.get_key("jt:lib") == {}


# ---------------------------------------------------------------------------
# Atomic commit
# ---------------------------------------------------------------------------


class TestAtomicCommit:
    def test_commit_uses_os_replace(self, make_db, db_path, monkeypatch):
        db = make_db()
        replace_calls = []

        real_replace = os.replace

        def tracking_replace(src, dst):
            replace_calls.append((src, dst))
            return real_replace(src, dst)

        monkeypatch.setattr(pickle_db_mod.os, "replace", tracking_replace)
        db.set_item("jt:watch", "tt123", {"progress": 50})

        assert len(replace_calls) == 1
        src, dst = replace_calls[0]
        # tmp file lives in the same directory and replace targets the db file
        assert os.path.dirname(src) == os.path.dirname(dst) == os.path.dirname(db_path)
        assert dst == db_path
        assert src.endswith(".tmp")

    def test_failed_serialization_keeps_previous_file_intact(self, make_db, db_path):
        db1 = make_db()
        db1.set_item("jt:watch", "tt123", {"progress": 50})
        with open(db_path, "rb") as f:
            good_bytes = f.read()

        # Force pickle.dump to blow up mid-write.
        original_dump = pickle_db_mod.pickle.dump
        pickle_db_mod.pickle.dump = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        try:
            db1.set_item("jt:watch", "tt456", {"progress": 90})
        finally:
            pickle_db_mod.pickle.dump = original_dump

        # Target file is untouched and no tmp files are left behind.
        with open(db_path, "rb") as f:
            assert f.read() == good_bytes
        leftovers = [n for n in os.listdir(os.path.dirname(db_path)) if n != "database.pickle"]
        assert leftovers == []

        # In-memory state still holds the uncommitted change.
        assert db1.get_item("jt:watch", "tt456") == {"progress": 90}

    def test_no_tmp_files_left_after_successful_commit(self, make_db, db_path):
        db = make_db()
        for i in range(5):
            db.set_item("jt:watch", f"tt{i}", {"i": i})
        leftovers = [n for n in os.listdir(os.path.dirname(db_path)) if n != "database.pickle"]
        assert leftovers == []

    def test_written_file_is_valid_pickle(self, make_db, db_path):
        db = make_db()
        db.set_item("jt:watch", "tt123", {"progress": 50})
        with open(db_path, "rb") as f:
            data = pickle.load(f)
        assert data["jt:watch"]["tt123"] == {"progress": 50}
