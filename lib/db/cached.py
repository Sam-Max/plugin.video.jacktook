import os
import pickle
import sqlite3
import sys
import threading
import traceback

from base64 import b64encode, b64decode
from datetime import datetime, timedelta
from hashlib import sha256

from lib.jacktook.utils import kodilog

import xbmcaddon
import xbmc
import xbmcgui

PY3 = sys.version_info.major >= 3
if PY3:
    from xbmcvfs import translatePath
else:
    from xbmc import translatePath

ADDON_DATA = translatePath(
    xbmcaddon.Addon("plugin.video.jacktook").getAddonInfo("profile")
)
ADDON_ID = xbmcaddon.Addon().getAddonInfo("id")

if not PY3:
    ADDON_DATA = ADDON_DATA.decode("utf-8")

if not os.path.exists(ADDON_DATA):
    os.makedirs(ADDON_DATA)

SQLITE_SETTINGS = {
    "journal_mode": "wal",
    "auto_vacuum": "full",
    "cache_size": 8 * 1024,
    "mmap_size": 64 * 1024 * 1024,
    "synchronous": "normal",
}


def pickle_hash(obj):
    data = pickle.dumps(obj)
    h = sha256()
    h.update(data)
    return h.hexdigest()


class _BaseCache(object):
    __instance = None

    _load_func = staticmethod(pickle.loads)
    _dump_func = staticmethod(pickle.dumps)
    _hash_func = staticmethod(pickle_hash)

    @classmethod
    def get_instance(cls):
        if cls.__instance is None:
            cls.__instance = cls()
        return cls.__instance

    def _get(self, key, default=None, hashed_key=False, identifier=""):
        result = self._get(self._generate_key(key, hashed_key, identifier))
        ret = default
        if result:
            data, expires = result
            if expires > datetime.utcnow():
                ret = self._process(data)
        return ret

    def _set(self, key, data, expiry_time, hashed_key=False, identifier=""):
        if expiry_time == timedelta(0):
            return  # Do nothing, as it will expire immediately

        self._set(
            self._generate_key(key, hashed_key, identifier),
            self._prepare(data),
            datetime.utcnow() + expiry_time,
        )

    def close(self):
        pass

    def _generate_key(self, key, hashed_key=False, identifier=""):
        if not hashed_key:
            key = self._hash_func(key)
        if identifier:
            key += identifier
        return key

    def _process(self, obj):
        return obj

    def _prepare(self, s):
        return s


class RuntimeCache:
    _store = {}

    @classmethod
    def set(cls, key, value):
        cls._store[key] = value

    @classmethod
    def get(cls, key):
        return cls._store.get(key)

    @classmethod
    def delete(cls, key):
        if key in cls._store:
            del cls._store[key]

    @classmethod
    def clear(cls):
        cls._store.clear()


class MemoryCache(_BaseCache):
    def __init__(self, database=ADDON_ID):
        self._window = xbmcgui.Window(10000)
        self._database = database + "."

    def get(self, key):
        data = self._window.getProperty(self._database + key)
        if data:
            decoded_data = self._load_func(b64decode(data))
            return decoded_data

    def set(self, key, data):
        try:
            blob = self._dump_func(data)
            self._window.setProperty(self._database + key, b64encode(blob).decode())
        except Exception as e:
            kodilog(f"[MemoryCache] Error storing key {key!r}: {str(e)}")
            kodilog(traceback.format_exc())

    def delete(self, key):
        self._window.clearProperty(self._database + key)


class SQLiteCache(_BaseCache):
    def __init__(
        self,
        database=os.path.join(ADDON_DATA, ADDON_ID + ".cached.sqlite"),
        cleanup_interval=timedelta(minutes=15),
    ):
        self._conn = sqlite3.connect(
            database,
            detect_types=sqlite3.PARSE_DECLTYPES,
            isolation_level=None,
            check_same_thread=False,
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS `cached` ("
            "key TEXT PRIMARY KEY NOT NULL, "
            "data BLOB NOT NULL, "
            "expires TIMESTAMP NOT NULL"
            ")"
        )
        for k, v in SQLITE_SETTINGS.items():
            self._conn.execute("PRAGMA {}={}".format(k, v))
        self._cleanup_interval = cleanup_interval
        self._last_cleanup = datetime.utcnow()
        self.clean_up()
        self._object_store = {}  # store raw objects that can't be pickled
        self._lock = threading.Lock()

    def _process(self, obj):
        return self._load_func(obj)

    def _prepare(self, s):
        return self._dump_func(s)

    def add_to_list(self, key, item, expires):
        """Append an item to a list stored under the given key."""
        existing_data = self.get_list(key)
        existing_data.append(item)
        self.set(
            key,
            existing_data,
            expires,
        )

    def get_list(self, key):
        """Retrieve the list stored under the given key."""
        result = self.get(key)
        if result:
            kodilog("Retrieved list for key '{}'".format(key))
            kodilog("List content: {}".format(result))
            return [tuple(item) for item in result]
        return []

    def get(self, key):
        with self._lock:
            if key in self._object_store:
                data, expires = self._object_store[key]
                if expires > datetime.utcnow():
                    return data
                else:
                    del self._object_store[key]
                    return None
            self.check_clean_up()
            try:
                result = self._conn.execute(
                    "SELECT data, expires FROM `cached` WHERE key = ?", (key,)
                ).fetchone()
            except Exception as e:
                kodilog(f"SQL error for key {key!r}: {e}")
                kodilog(traceback.format_exc())
                return None
            if result:
                data, expires = result
                if expires > datetime.utcnow():
                    return self._process(data)
            return None

    def set(self, key, data, expires):
        with self._lock:
            try:
                self.check_clean_up()
                self._conn.execute(
                    "INSERT OR REPLACE INTO `cached` (key, data, expires) VALUES(?, ?, ?)",
                    (
                        key,
                        sqlite3.Binary(self._prepare(data)),
                        datetime.utcnow() + expires,
                    ),
                )
                kodilog(
                    "Set cache for key '{}' with expiry {}".format(key, expires),
                    level=xbmc.LOGDEBUG,
                )
            except Exception as e:
                kodilog("Failed to set cache for key '{}': {}".format(key, str(e)))
                # fallback to raw in‑memory store
                self._object_store[key] = (data, expires)

    def clear_list(self, key):
        """Clear the list stored under the given key."""
        self.set(
            key,
            self._prepare([]),
            datetime.utcnow(),  # Set an immediate expiry to clear the list
        )

    def delete(self, key):
        """Remove a single key from the SQLite store."""
        self._conn.execute("DELETE FROM `cached` WHERE key = ?", (key,))

    def _set_version(self, version):
        self._conn.execute("PRAGMA user_version={}".format(version))

    @property
    def version(self):
        return self._conn.execute("PRAGMA user_version").fetchone()[0]

    @property
    def needs_cleanup(self):
        return self._last_cleanup + self._cleanup_interval < datetime.utcnow()

    def clean_up(self):
        self._conn.execute(
            "DELETE FROM `cached` WHERE expires <= STRFTIME('%Y-%m-%d %H:%M:%f', 'NOW')"
        )
        self._last_cleanup = datetime.utcnow()

    def clean_all(self):
        self._conn.execute("DELETE FROM cached")
        self._object_store.clear()

    def check_clean_up(self):
        clean_up = self.needs_cleanup
        if clean_up:
            self.clean_up()
        return clean_up

    def close(self):
        self._conn.close()


cache = SQLiteCache()
