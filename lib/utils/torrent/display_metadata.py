"""Shared, local display metadata for TorrServer torrents."""

import hashlib
import os
import re
import sqlite3
import time
from urllib.parse import urlsplit

from xbmcvfs import translatePath


DATABASE_URI = "special://profile/addon_data/jacktorr.shared/torrent-display-v1.sqlite"
SCHEMA_VERSION = 1
TTL_SECONDS = 365 * 24 * 60 * 60
MAX_CLEANUP_ROWS = 100
MAX_ROWS_PER_NAMESPACE = 2000
_INFO_HASH_RE = re.compile(r"^[0-9a-f]{40}$")


def _database_path(database_path=None):
    return database_path or translatePath(DATABASE_URI)


def _namespace(base_url):
    try:
        parsed = urlsplit(str(base_url or "").strip())
        scheme = parsed.scheme.lower()
        host = (parsed.hostname or "").lower()
        port = parsed.port
        if not scheme or not host or port is None:
            return ""
        return hashlib.sha256("{}://{}:{}".format(scheme, host, port).encode("utf-8")).hexdigest()[:16]
    except (TypeError, ValueError):
        return ""


def _info_hash(value):
    value = str(value or "").strip().lower()
    return value if _INFO_HASH_RE.match(value) else ""


def _text(value):
    if not isinstance(value, str):
        return ""
    return value[:16384]


def _connect(database_path=None):
    path = _database_path(database_path)
    connection = None
    try:
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        connection = sqlite3.connect(path, timeout=1)
        connection.execute("PRAGMA busy_timeout = 1000")
        with connection:
            if not _initialize(connection):
                connection.close()
                return None
        return connection
    except (OSError, sqlite3.Error):
        if connection is not None:
            connection.close()
        return None


def _initialize(connection):
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version not in (0, SCHEMA_VERSION):
        return False
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS torrent_display (
            namespace TEXT NOT NULL,
            info_hash TEXT NOT NULL,
            title TEXT NOT NULL,
            plot TEXT NOT NULL,
            poster TEXT NOT NULL,
            updated_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            PRIMARY KEY (namespace, info_hash)
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS torrent_display_expiry ON torrent_display (namespace, expires_at)"
    )
    connection.execute("PRAGMA user_version = {}".format(SCHEMA_VERSION))
    return True


def save_display_metadata(base_url, info_hash, title="", plot="", poster="", database_path=None):
    namespace = _namespace(base_url)
    info_hash = _info_hash(info_hash)
    title, plot, poster = _text(title), _text(plot), _text(poster)
    if not namespace or not info_hash or not any((title, plot, poster)):
        return False

    connection = _connect(database_path)
    if connection is None:
        return False
    try:
        now = int(time.time())
        with connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO torrent_display
                (namespace, info_hash, title, plot, poster, updated_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (namespace, info_hash, title, plot, poster, now, now + TTL_SECONDS),
            )
        return True
    except sqlite3.Error:
        return False
    finally:
        connection.close()


def get_display_metadata(base_url, info_hash, database_path=None):
    namespace = _namespace(base_url)
    info_hash = _info_hash(info_hash)
    if not namespace or not info_hash:
        return {}

    connection = _connect(database_path)
    if connection is None:
        return {}
    try:
        row = connection.execute(
            """
            SELECT title, plot, poster FROM torrent_display
            WHERE namespace = ? AND info_hash = ? AND expires_at > ?
            """,
            (namespace, info_hash, int(time.time())),
        ).fetchone()
        return {"title": row[0], "plot": row[1], "poster": row[2]} if row else {}
    except sqlite3.Error:
        return {}
    finally:
        connection.close()


def delete_display_metadata(base_url, info_hash, database_path=None):
    namespace = _namespace(base_url)
    info_hash = _info_hash(info_hash)
    if not namespace or not info_hash:
        return False

    connection = _connect(database_path)
    if connection is None:
        return False
    try:
        with connection:
            connection.execute(
                "DELETE FROM torrent_display WHERE namespace = ? AND info_hash = ?",
                (namespace, info_hash),
            )
        return True
    except sqlite3.Error:
        return False
    finally:
        connection.close()


def prune_display_metadata(base_url, database_path=None):
    namespace = _namespace(base_url)
    if not namespace:
        return False

    connection = _connect(database_path)
    if connection is None:
        return False
    try:
        with connection:
            connection.execute(
                """
                DELETE FROM torrent_display WHERE rowid IN (
                    SELECT rowid FROM torrent_display
                    WHERE namespace = ? AND expires_at <= ?
                    ORDER BY expires_at LIMIT ?
                )
                """,
                (namespace, int(time.time()), MAX_CLEANUP_ROWS),
            )
            connection.execute(
                """
                DELETE FROM torrent_display WHERE rowid IN (
                    SELECT rowid FROM torrent_display
                    WHERE namespace = ? ORDER BY updated_at LIMIT ?
                ) AND (SELECT COUNT(*) FROM torrent_display WHERE namespace = ?) > ?
                """,
                (namespace, MAX_CLEANUP_ROWS, namespace, MAX_ROWS_PER_NAMESPACE),
            )
        return True
    except sqlite3.Error:
        return False
    finally:
        connection.close()
