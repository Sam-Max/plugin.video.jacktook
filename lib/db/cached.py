import os
import pickle
import sqlite3
import sys
from base64 import b64encode, b64decode
from datetime import datetime, timedelta
from functools import wraps
from hashlib import sha256

import xbmcaddon
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

# Sqlite pragmas, according to https://www.sqlite.org/pragma.html
SQLITE_SETTINGS = {
    "journal_mode": "wal",
    "auto_vacuum": "full",
    "cache_size": 8 * 1024,
    "mmap_size": 64 * 1024 * 1024,
    "synchronous": "normal",
}


def pickle_hash(obj):
    data = pickle.dumps(obj)
    # We could also use zlib.adler32 here
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

    def get(self, key, default=None, hashed_key=False, identifier=""):
        result = self._get(self._generate_key(key, hashed_key, identifier))
        ret = default
        if result:
            data, expires = result
            if expires > datetime.utcnow():
                ret = self._process(data)
        return ret

    def set(self, key, data, expiry_time, hashed_key=False, identifier=""):
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

    def _get(self, key):
        raise NotImplementedError("_get needs to be implemented")

    def _set(self, key, data, expires):
        raise NotImplementedError("_set needs to be implemented")


class MemoryCache(_BaseCache):
    def __init__(self, database=ADDON_ID):
        self._window = xbmcgui.Window(10000)
        self._database = database + "."

    def _get(self, key):
        data = self._window.getProperty(self._database + key)
        return self._load_func(b64decode(data)) if data else None

    def _set(self, key, data, expires):
        self._window.setProperty(
            self._database + key, b64encode(self._dump_func((data, expires))).decode()
        )


class Cache(_BaseCache):
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

    def _process(self, obj):
        return self._load_func(obj)

    def _prepare(self, s):
        return self._dump_func(s)

    def _get(self, key):
        self.check_clean_up()
        return self._conn.execute(
            "SELECT data, expires FROM `cached` WHERE key = ?", (key,)
        ).fetchone()

    def _set(self, key, data, expires):
        self.check_clean_up()
        self._conn.execute(
            "INSERT OR REPLACE INTO `cached` (key, data, expires) VALUES(?, ?, ?)",
            (key, sqlite3.Binary(data), expires),
        )

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

    def check_clean_up(self):
        clean_up = self.needs_cleanup
        if clean_up:
            self.clean_up()
        return clean_up

    def close(self):
        self._conn.close()


class LoadingCache(object):
    def __init__(self, expiry_time, loader, cache_type, *args, **kwargs):
        self._expiry_time = expiry_time
        self._loader = loader
        self._hashed_key = kwargs.pop("hashed_key", False)
        self._identifier = kwargs.pop("identifier", "")
        self._cache = cache_type(*args, **kwargs)
        self._sentinel = object()

    def get(self, key):
        data = self._cache.get(
            key,
            default=self._sentinel,
            hashed_key=self._hashed_key,
            identifier=self._identifier,
        )
        if data is self._sentinel:
            data = self._loader(key)
            self._cache.set(
                key,
                data,
                self._expiry_time,
                hashed_key=self._hashed_key,
                identifier=self._identifier,
            )
        return data

    def close(self):
        self._cache.close()


def cached(expiry_time, ignore_self=False, identifier="", cache_type=Cache):
    def decorator(func):
        sentinel = object()
        cache = cache_type.get_instance()

        @wraps(func)
        def wrapper(*args, **kwargs):
            key_args = args[1:] if ignore_self else args
            # noinspection PyProtectedMember
            key = cache._generate_key((key_args, kwargs), identifier=identifier)
            result = cache.get(key, default=sentinel, hashed_key=True)
            if result is sentinel:
                result = func(*args, **kwargs)
                cache.set(key, result, expiry_time, hashed_key=True)

            return result

        return wrapper

    return decorator


# noinspection PyTypeChecker
def memory_cached(expiry_time, instance_method=False, identifier=""):
    return cached(expiry_time, instance_method, identifier, MemoryCache)
