"""SQLite mirror for the Nuvio profile library.

``NuvioSyncService`` writes the mirror and the offline Movies/Shows view reads
it. The store reuses the ``base_cache`` profile database location and connect
semantics (timeout, autocommit isolation, OFF pragmas) so it behaves like the
other local caches.

The store accepts an injected connection (or a zero-argument factory) so tests
can run against a real in-memory database even though ``tests/conftest.py``
globally mocks ``sqlite3.connect``.
"""

import contextlib
import json
import os
import sqlite3
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from lib.api.trakt.base_cache import database_timeout, databases_path
from lib.db.cached import cache
from lib.utils.kodi.utils import kodilog

SCHEMA_VERSION = 2
DATABASE_FILENAME = "nuvio.db"

LIBRARY_TABLE = "nuvio_library"
META_TABLE = "nuvio_library_meta"
CLIENT_META_TABLE = "nuvio_client_meta"

ORIGIN_CLIENT_ID_KEY = "origin_client_id"

_CREATE_LIBRARY_TABLE = f"""
CREATE TABLE IF NOT EXISTS {LIBRARY_TABLE} (
    profile_id INTEGER NOT NULL,
    item_key TEXT NOT NULL,
    content_type TEXT NOT NULL,
    content_id TEXT NOT NULL,
    tmdb_id INTEGER,
    title TEXT,
    poster TEXT,
    background TEXT,
    description TEXT,
    release_info TEXT,
    imdb_rating REAL,
    genres TEXT,
    addon_base_url TEXT,
    added_at_ms INTEGER,
    last_event_id INTEGER NOT NULL DEFAULT 0,
    updated_at_ms INTEGER,
    PRIMARY KEY (profile_id, item_key)
)
"""

_CREATE_LIBRARY_INDEX = (
    f"CREATE INDEX IF NOT EXISTS idx_{LIBRARY_TABLE}_profile_type "
    f"ON {LIBRARY_TABLE} (profile_id, content_type)"
)

_CREATE_META_TABLE = f"""
CREATE TABLE IF NOT EXISTS {META_TABLE} (
    profile_id INTEGER PRIMARY KEY,
    cursor_event_id INTEGER NOT NULL DEFAULT 0,
    snapshot_done INTEGER NOT NULL DEFAULT 0,
    last_sync_ms INTEGER
)
"""

# Install-scoped metadata (e.g. the stable origin client id attached to library
# writes). It is global rather than per-profile, so it has no profile column.
_CREATE_CLIENT_META_TABLE = f"""
CREATE TABLE IF NOT EXISTS {CLIENT_META_TABLE} (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
)
"""

_ITEM_COLUMNS = (
    "(profile_id, item_key, content_type, content_id, tmdb_id, title, poster, "
    "background, description, release_info, imdb_rating, genres, addon_base_url, "
    "added_at_ms, last_event_id, updated_at_ms)"
)
_ITEM_PLACEHOLDERS = "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
_ITEM_UPDATE_ASSIGNMENTS = """
    content_type = excluded.content_type,
    content_id = excluded.content_id,
    tmdb_id = excluded.tmdb_id,
    title = excluded.title,
    poster = excluded.poster,
    background = excluded.background,
    description = excluded.description,
    release_info = excluded.release_info,
    imdb_rating = excluded.imdb_rating,
    genres = excluded.genres,
    addon_base_url = excluded.addon_base_url,
    added_at_ms = excluded.added_at_ms,
    last_event_id = excluded.last_event_id,
    updated_at_ms = excluded.updated_at_ms
"""

# Deltas only overwrite when the incoming event is not older than the stored
# one, so a later event wins even if a batch ever arrives out of order.
_UPSERT_ITEM = f"""
INSERT INTO {LIBRARY_TABLE} {_ITEM_COLUMNS}
VALUES {_ITEM_PLACEHOLDERS}
ON CONFLICT(profile_id, item_key) DO UPDATE SET{_ITEM_UPDATE_ASSIGNMENTS}
WHERE excluded.last_event_id >= {LIBRARY_TABLE}.last_event_id
"""

# A snapshot page is the authoritative full state for its rows, so it always
# refreshes the stored columns.
_UPSERT_SNAPSHOT_ITEM = f"""
INSERT INTO {LIBRARY_TABLE} {_ITEM_COLUMNS}
VALUES {_ITEM_PLACEHOLDERS}
ON CONFLICT(profile_id, item_key) DO UPDATE SET{_ITEM_UPDATE_ASSIGNMENTS}
"""

_UPSERT_META_CURSOR = f"""
INSERT INTO {META_TABLE} (profile_id, cursor_event_id, snapshot_done, last_sync_ms)
VALUES (?, ?, 0, ?)
ON CONFLICT(profile_id) DO UPDATE SET
    cursor_event_id = excluded.cursor_event_id,
    last_sync_ms = excluded.last_sync_ms
"""

_BEGIN_SNAPSHOT = f"""
INSERT INTO {META_TABLE} (profile_id, cursor_event_id, snapshot_done, last_sync_ms)
VALUES (?, 0, 0, NULL)
ON CONFLICT(profile_id) DO UPDATE SET snapshot_done = 0
"""

_FINISH_SNAPSHOT = f"""
INSERT INTO {META_TABLE} (profile_id, cursor_event_id, snapshot_done, last_sync_ms)
VALUES (?, ?, 1, ?)
ON CONFLICT(profile_id) DO UPDATE SET
    cursor_event_id = excluded.cursor_event_id,
    snapshot_done = 1,
    last_sync_ms = excluded.last_sync_ms
"""


def nuvio_database_path() -> str:
    """Return the absolute path of the Nuvio mirror database."""
    return os.path.join(databases_path, DATABASE_FILENAME)


def _now_ms() -> int:
    return int(time.time() * 1000)


def _string_or_none(value: Any) -> Optional[str]:
    return value if isinstance(value, str) else None


def _coerce_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_float(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_non_negative_int(value: Any) -> Optional[int]:
    parsed = _coerce_int(value)
    return parsed if parsed is not None and parsed >= 0 else None


def _coerce_profile_id(profile_id: Any) -> Optional[int]:
    parsed = _coerce_int(profile_id)
    return parsed if parsed is not None and parsed > 0 else None


def _encode_genres(genres: Any) -> str:
    if not isinstance(genres, list):
        return json.dumps([])
    cleaned = [entry.strip() for entry in genres if isinstance(entry, str) and entry.strip()]
    return json.dumps(cleaned)


def _decode_genres(value: Any) -> List[str]:
    if not isinstance(value, str) or not value:
        return []
    try:
        decoded = json.loads(value)
    except ValueError:
        return []
    if not isinstance(decoded, list):
        return []
    return [entry for entry in decoded if isinstance(entry, str)]


def _open_connection() -> Any:
    database_path = nuvio_database_path()
    directory = os.path.dirname(database_path)
    if directory and not os.path.isdir(directory):
        os.makedirs(directory, exist_ok=True)
    connection = sqlite3.connect(
        database_path,
        timeout=database_timeout,
        isolation_level=None,
        check_same_thread=False,
    )
    connection.execute("PRAGMA synchronous = OFF")
    connection.execute("PRAGMA journal_mode = OFF")
    connection.row_factory = sqlite3.Row
    return connection


def _create_schema(connection: Any) -> None:
    connection.execute(_CREATE_LIBRARY_TABLE)
    connection.execute(_CREATE_LIBRARY_INDEX)
    connection.execute(_CREATE_META_TABLE)
    connection.execute(_CREATE_CLIENT_META_TABLE)
    connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def setup_nuvio_database(connection: Any = None) -> bool:
    """Create the mirror schema idempotently, opening a connection if needed."""
    owns_connection = connection is None
    if owns_connection:
        connection = _open_connection()
    try:
        _create_schema(connection)
        return True
    except Exception as error:
        kodilog(f"[NUVIO] mirror schema setup failed ({type(error).__name__})")
        return False
    finally:
        if owns_connection:
            with contextlib.suppress(Exception):
                connection.close()


class NuvioStore:
    """Per-profile SQLite mirror of the Nuvio library."""

    def __init__(self, connection: Union[Any, Callable[[], Any], None] = None):
        self._owns_connection = connection is None
        # ``sqlite3.Connection`` is callable in modern CPython, so detect a live
        # DB-API connection by capability before treating the value as a factory.
        if connection is None:
            self._connection = _open_connection()
        elif hasattr(connection, "execute"):
            self._connection = connection
        elif callable(connection):
            self._connection = connection()
        else:
            self._connection = connection
        self._configure_connection(self._connection)

    @staticmethod
    def _configure_connection(connection: Any) -> None:
        with contextlib.suppress(Exception):
            connection.row_factory = sqlite3.Row
        with contextlib.suppress(Exception):
            connection.isolation_level = None

    @property
    def connection(self) -> Any:
        return self._connection

    def close(self) -> None:
        if self._owns_connection and self._connection is not None:
            with contextlib.suppress(Exception):
                self._connection.close()

    def setup_nuvio_database(self) -> bool:
        return setup_nuvio_database(self._connection)

    def apply_delta(
        self,
        profile_id: Any,
        events: Any,
        cursor_event_id: Any,
    ) -> bool:
        """Apply delta events and the cursor in a single transaction.

        Events apply in ascending ``event_id`` order and any event at or below
        the stored cursor is skipped. On any failure the transaction rolls back
        so both rows and cursor stay untouched and the batch can be replayed.
        """
        profile = _coerce_profile_id(profile_id)
        if profile is None:
            return False
        normalized = self._normalize_events(events)
        if normalized is None:
            return False
        cursor = _coerce_non_negative_int(cursor_event_id)
        connection = self._connection
        try:
            connection.execute("BEGIN IMMEDIATE")
            current = self._read_cursor(connection, profile)
            for event in normalized:
                if event["event_id"] <= current:
                    continue
                self._apply_event(connection, profile, event)
            advanced = current if cursor is None else max(current, cursor)
            self._write_meta_cursor(connection, profile, advanced)
            connection.execute("COMMIT")
            return True
        except Exception as error:
            with contextlib.suppress(Exception):
                connection.execute("ROLLBACK")
            kodilog(f"[NUVIO] mirror apply_delta failed ({type(error).__name__})")
            return False

    def begin_snapshot(self, profile_id: Any) -> bool:
        """Clear the profile rows and mark the snapshot incomplete."""
        profile = _coerce_profile_id(profile_id)
        if profile is None:
            return False
        connection = self._connection
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                f"DELETE FROM {LIBRARY_TABLE} WHERE profile_id = ?",
                (profile,),
            )
            connection.execute(_BEGIN_SNAPSHOT, (profile,))
            connection.execute("COMMIT")
            return True
        except Exception as error:
            with contextlib.suppress(Exception):
                connection.execute("ROLLBACK")
            kodilog(f"[NUVIO] mirror begin_snapshot failed ({type(error).__name__})")
            return False

    def write_snapshot_items(self, profile_id: Any, items: Any) -> bool:
        """Write one snapshot page of items for the profile."""
        profile = _coerce_profile_id(profile_id)
        if profile is None:
            return False
        normalized = self._normalize_snapshot_items(items)
        if normalized is None:
            return False
        if not normalized:
            return True
        now_ms = _now_ms()
        rows = [
            self._item_values(profile, item_key, item, 0, now_ms) for item_key, item in normalized
        ]
        connection = self._connection
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.executemany(_UPSERT_SNAPSHOT_ITEM, rows)
            connection.execute("COMMIT")
            return True
        except Exception as error:
            with contextlib.suppress(Exception):
                connection.execute("ROLLBACK")
            kodilog(f"[NUVIO] mirror snapshot write failed ({type(error).__name__})")
            return False

    def finish_snapshot(self, profile_id: Any, cursor_event_id: Any) -> bool:
        """Mark the snapshot complete and persist the captured cursor."""
        profile = _coerce_profile_id(profile_id)
        if profile is None:
            return False
        cursor = _coerce_non_negative_int(cursor_event_id)
        if cursor is None:
            cursor = 0
        connection = self._connection
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(_FINISH_SNAPSHOT, (profile, cursor, _now_ms()))
            connection.execute("COMMIT")
            return True
        except Exception as error:
            with contextlib.suppress(Exception):
                connection.execute("ROLLBACK")
            kodilog(f"[NUVIO] mirror finish_snapshot failed ({type(error).__name__})")
            return False

    def get_or_create_origin_client_id(self) -> str:
        """Return the stable per-install origin client id, generating once.

        The value is persisted in the mirror database so every library write
        from this installation carries the same identity.
        """
        connection = self._connection
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                f"SELECT value FROM {CLIENT_META_TABLE} WHERE key = ?",
                (ORIGIN_CLIENT_ID_KEY,),
            ).fetchone()
            if row is not None and isinstance(row[0], str) and row[0].strip():
                connection.execute("COMMIT")
                return row[0]
            origin_client_id = uuid.uuid4().hex
            connection.execute(
                f"INSERT INTO {CLIENT_META_TABLE} (key, value) VALUES (?, ?) "
                f"ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (ORIGIN_CLIENT_ID_KEY, origin_client_id),
            )
            connection.execute("COMMIT")
            return origin_client_id
        except Exception as error:
            with contextlib.suppress(Exception):
                connection.execute("ROLLBACK")
            kodilog(f"[NUVIO] origin client id failed ({type(error).__name__})")
            return ""

    def upsert_items(self, profile_id: Any, items: Any) -> bool:
        """Write normalized mirror items locally after a successful push.

        The profile cursor is left untouched: ``last_event_id`` is set to the
        current cursor so a later remote delta event (a higher id) still wins.
        """
        profile = _coerce_profile_id(profile_id)
        if profile is None:
            return False
        normalized = self._normalize_snapshot_items(items)
        if normalized is None:
            return False
        if not normalized:
            return True
        connection = self._connection
        try:
            connection.execute("BEGIN IMMEDIATE")
            cursor = self._read_cursor(connection, profile)
            now_ms = _now_ms()
            rows = [
                self._item_values(profile, item_key, item, cursor, now_ms)
                for item_key, item in normalized
            ]
            connection.executemany(_UPSERT_SNAPSHOT_ITEM, rows)
            connection.execute("COMMIT")
            return True
        except Exception as error:
            with contextlib.suppress(Exception):
                connection.execute("ROLLBACK")
            kodilog(f"[NUVIO] mirror upsert_items failed ({type(error).__name__})")
            return False

    def delete_items(self, profile_id: Any, keys: Any) -> bool:
        """Delete explicit mirror rows by ``content_type:content_id`` item key.

        The profile cursor is left untouched. Returns ``False`` on any failure.
        """
        profile = _coerce_profile_id(profile_id)
        if profile is None:
            return False
        normalized = self._normalize_snapshot_items(keys)
        if normalized is None:
            return False
        if not normalized:
            return True
        connection = self._connection
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.executemany(
                f"DELETE FROM {LIBRARY_TABLE} WHERE profile_id = ? AND item_key = ?",
                [(profile, item_key) for item_key, _item in normalized],
            )
            connection.execute("COMMIT")
            return True
        except Exception as error:
            with contextlib.suppress(Exception):
                connection.execute("ROLLBACK")
            kodilog(f"[NUVIO] mirror delete_items failed ({type(error).__name__})")
            return False

    def get_meta(self, profile_id: Any) -> Optional[Dict[str, Any]]:
        """Return the profile mirror metadata, defaulted when unset."""
        profile = _coerce_profile_id(profile_id)
        if profile is None:
            return None
        row = self._connection.execute(
            f"SELECT profile_id, cursor_event_id, snapshot_done, last_sync_ms "
            f"FROM {META_TABLE} WHERE profile_id = ?",
            (profile,),
        ).fetchone()
        if row is None:
            return {
                "profile_id": profile,
                "cursor_event_id": 0,
                "snapshot_done": 0,
                "last_sync_ms": None,
            }
        return {
            "profile_id": row["profile_id"],
            "cursor_event_id": row["cursor_event_id"],
            "snapshot_done": row["snapshot_done"],
            "last_sync_ms": row["last_sync_ms"],
        }

    def get_cursor_event_id(self, profile_id: Any) -> int:
        profile = _coerce_profile_id(profile_id)
        if profile is None:
            return 0
        return self._read_cursor(self._connection, profile)

    def list_items(self, profile_id: Any, content_type: Any) -> List[Dict[str, Any]]:
        profile = _coerce_profile_id(profile_id)
        if profile is None or content_type not in ("movie", "series"):
            return []
        rows = self._connection.execute(
            f"SELECT * FROM {LIBRARY_TABLE} WHERE profile_id = ? AND content_type = ? "
            f"ORDER BY added_at_ms DESC, item_key ASC",
            (profile, content_type),
        ).fetchall()
        return [self._row_to_item(row) for row in rows]

    def count(self, profile_id: Any) -> int:
        profile = _coerce_profile_id(profile_id)
        if profile is None:
            return 0
        row = self._connection.execute(
            f"SELECT COUNT(*) FROM {LIBRARY_TABLE} WHERE profile_id = ?",
            (profile,),
        ).fetchone()
        return int(row[0]) if row is not None else 0

    @staticmethod
    def _read_cursor(connection: Any, profile_id: int) -> int:
        row = connection.execute(
            f"SELECT cursor_event_id FROM {META_TABLE} WHERE profile_id = ?",
            (profile_id,),
        ).fetchone()
        if row is None:
            return 0
        cursor = _coerce_non_negative_int(row[0])
        return cursor if cursor is not None else 0

    def _write_meta_cursor(self, connection: Any, profile_id: int, cursor: int) -> None:
        connection.execute(_UPSERT_META_CURSOR, (profile_id, cursor, _now_ms()))

    def _apply_event(self, connection: Any, profile_id: int, event: Dict[str, Any]) -> None:
        item_key = f"{event['content_type']}:{event['content_id']}"
        if event["operation"] == "delete":
            connection.execute(
                f"DELETE FROM {LIBRARY_TABLE} WHERE profile_id = ? AND item_key = ?",
                (profile_id, item_key),
            )
            return
        connection.execute(
            _UPSERT_ITEM,
            self._item_values(profile_id, item_key, event, event["event_id"], _now_ms()),
        )

    @staticmethod
    def _item_values(
        profile_id: int,
        item_key: str,
        item: Dict[str, Any],
        last_event_id: int,
        updated_at_ms: int,
    ) -> Tuple[Any, ...]:
        added_at_ms = _coerce_non_negative_int(item.get("added_at_ms"))
        return (
            profile_id,
            item_key,
            item.get("content_type"),
            item.get("content_id"),
            _coerce_int(item.get("tmdb_id")),
            _string_or_none(item.get("title")),
            _string_or_none(item.get("poster")),
            _string_or_none(item.get("background")),
            _string_or_none(item.get("description")),
            _string_or_none(item.get("release_info")),
            _coerce_float(item.get("imdb_rating")),
            _encode_genres(item.get("genres")),
            _string_or_none(item.get("addon_base_url")),
            0 if added_at_ms is None else added_at_ms,
            last_event_id,
            updated_at_ms,
        )

    @staticmethod
    def _normalize_events(events: Any) -> Optional[List[Dict[str, Any]]]:
        if events is None:
            return []
        if not isinstance(events, (list, tuple)):
            return None
        normalized: List[Dict[str, Any]] = []
        for event in events:
            if not isinstance(event, dict):
                return None
            if event.get("operation") not in ("upsert", "delete"):
                return None
            event_id = _coerce_int(event.get("event_id"))
            if event_id is None or event_id <= 0:
                return None
            content_type = event.get("content_type")
            content_id = event.get("content_id")
            if content_type not in ("movie", "series"):
                return None
            if not isinstance(content_id, str) or not content_id.strip():
                return None
            normalized.append({**event, "event_id": event_id})
        normalized.sort(key=lambda entry: entry["event_id"])
        return normalized

    @staticmethod
    def _normalize_snapshot_items(items: Any) -> Optional[List[Tuple[str, Dict[str, Any]]]]:
        if items is None:
            return []
        if not isinstance(items, (list, tuple)):
            return None
        normalized: List[Tuple[str, Dict[str, Any]]] = []
        for item in items:
            if not isinstance(item, dict):
                return None
            content_type = item.get("content_type")
            content_id = item.get("content_id")
            if content_type not in ("movie", "series"):
                return None
            if not isinstance(content_id, str) or not content_id.strip():
                return None
            normalized.append((f"{content_type}:{content_id}", item))
        return normalized

    @staticmethod
    def _row_to_item(row: Any) -> Dict[str, Any]:
        return {
            "content_type": row["content_type"],
            "content_id": row["content_id"],
            "tmdb_id": row["tmdb_id"],
            "title": row["title"],
            "poster": row["poster"],
            "background": row["background"],
            "description": row["description"],
            "release_info": row["release_info"],
            "imdb_rating": row["imdb_rating"],
            "genres": _decode_genres(row["genres"]),
            "addon_base_url": row["addon_base_url"],
            "added_at_ms": row["added_at_ms"],
            "last_event_id": row["last_event_id"],
        }


def invalidate_nuvio_library_cache() -> None:
    """Drop cached Nuvio library view data after the mirror changes."""
    cache.delete_like("nuvio.library.%")
