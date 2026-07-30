import ast
import json

from lib.api.trakt.base_cache import connect_database
from lib.utils.kodi.utils import kodilog

SELECT = "SELECT id FROM trakt_data"
DELETE = "DELETE FROM trakt_data WHERE id=?"
DELETE_LIKE = 'DELETE FROM trakt_data WHERE id LIKE "%s"'
WATCHED_INSERT = "INSERT OR IGNORE INTO watched VALUES (?, ?, ?, ?, ?, ?)"
WATCHED_DELETE = "DELETE FROM watched WHERE db_type = ?"
PROGRESS_INSERT = "INSERT OR IGNORE INTO progress VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
PROGRESS_DELETE = "DELETE FROM progress WHERE db_type = ?"
STATUS_INSERT = "INSERT INTO watched_status VALUES (?, ?, ?)"
STATUS_DELETE = "DELETE FROM watched_status"
BASE_DELETE = "DELETE FROM %s"
TC_BASE_GET = "SELECT data FROM trakt_data WHERE id = ?"
TC_BASE_SET = "INSERT OR REPLACE INTO trakt_data (id, data) VALUES (?, ?)"
TC_BASE_DELETE = "DELETE FROM trakt_data WHERE id = ?"
MAX_TRAKT_LEGACY_LITERAL_SIZE = 128 * 1024  # Bound Python AST expansion for repr rows.
MAX_TRAKT_JSON_ROW_SIZE = 512 * 1024  # About 2x the measured 1,000-row normalized cache.


class TraktCache:
    def get(self, string, expected_type, item_type=None):
        result = None
        try:
            dbcon = connect_database("trakt_db")
            cache_data = dbcon.execute(TC_BASE_GET, (string,)).fetchone()
            if cache_data:
                result = _decode_cache_value(
                    cache_data[0], string, expected_type, item_type=item_type
                )
        except Exception:
            pass
        return result

    def set(self, string, data):
        try:
            encoded = _encode_cache_value(data, string)
            if encoded is None:
                return None
            dbcon = connect_database("trakt_db")
            dbcon.execute(TC_BASE_SET, (string, encoded))
        except Exception:
            return None

    def delete(self, string):
        try:
            dbcon = connect_database("trakt_db")
            dbcon.execute(TC_BASE_DELETE, (string,))
        except Exception:
            pass

    def clear_all(self):
        try:
            dbcon = connect_database("trakt_db")
            dbcon.execute("DELETE FROM trakt_data")
            dbcon.execute("VACUUM")
        except Exception:
            pass


trakt_cache = TraktCache()


class TraktWatched:
    def set_bulk_tvshow_status(self, insert_list):
        self._delete(STATUS_DELETE, ())
        self._executemany(STATUS_INSERT, insert_list)

    def set_tvshow_status(self, insert_dict):
        encoded = _encode_cache_value(insert_dict, "trakt_tvshow_status")
        if encoded is None:
            return
        dbcon = connect_database("trakt_db")
        dbcon.execute(
            "INSERT OR REPLACE INTO trakt_data (id, data) VALUES (?, ?)",
            (
                "trakt_tvshow_status",
                encoded,
            ),
        )

    def set_bulk_movie_watched(self, insert_list):
        self._delete(WATCHED_DELETE, ("movie",))
        self._executemany(WATCHED_INSERT, insert_list)

    def set_bulk_tvshow_watched(self, insert_list):
        self._delete(WATCHED_DELETE, ("episode",))
        self._executemany(WATCHED_INSERT, insert_list)

    def set_bulk_movie_progress(self, insert_list):
        self._delete(PROGRESS_DELETE, ("movie",))
        self._executemany(PROGRESS_INSERT, insert_list)

    def set_bulk_tvshow_progress(self, insert_list):
        self._delete(PROGRESS_DELETE, ("episode",))
        self._executemany(PROGRESS_INSERT, insert_list)

    def clear_all(self):
        try:
            self._delete("DELETE FROM watched", ())
            self._delete("DELETE FROM progress", ())
            self._delete("DELETE FROM watched_status", ())
        except Exception:
            pass

    def _executemany(self, command, insert_list):
        dbcon = connect_database("trakt_db")
        dbcon.executemany(command, insert_list)

    def _delete(self, command, args):
        dbcon = connect_database("trakt_db")
        dbcon.execute(command, args)
        dbcon.execute("VACUUM")

    def get_watched_status(self, db_type, media_id, season=None, episode=None):
        try:
            dbcon = connect_database("trakt_db")
            if db_type == "movie":
                command = "SELECT 1 FROM watched WHERE db_type=? AND media_id=?"
                args = (db_type, media_id)
            else:
                command = "SELECT 1 FROM watched WHERE db_type=? AND media_id=? AND season=? AND episode=?"
                args = (db_type, media_id, season, episode)

            result = dbcon.execute(command, args).fetchone()
            return result is not None
        except Exception:
            return False

    def get_progress(self, db_type, media_id, season=None, episode=None):
        try:
            dbcon = connect_database("trakt_db")
            if db_type == "movie":
                command = "SELECT resume_point FROM progress WHERE db_type=? AND media_id=?"
                args = (db_type, media_id)
            else:
                command = "SELECT resume_point FROM progress WHERE db_type=? AND media_id=? AND season=? AND episode=?"
                args = (db_type, media_id, season, episode)

            result = dbcon.execute(command, args).fetchone()
            if result:
                return float(result[0])
            return 0.0
        except Exception:
            return 0.0


trakt_watched_cache = TraktWatched()


def cache_trakt_object(function, string, url, expected_type, item_type=None):
    cache = trakt_cache.get(string, expected_type, item_type=item_type)
    if cache:
        return cache
    result = function(url)
    trakt_cache.set(string, result)
    return result


def get_activity():
    string = "trakt_get_activity"
    try:
        dbcon = connect_database("trakt_db")
        data = dbcon.execute(TC_BASE_GET, (string,)).fetchone()
        if data:
            activity = _decode_cache_value(data[0], string, dict)
            if activity is not None and _matches_required_activity_shape(
                activity, default_activities()
            ):
                return activity
            if activity is not None:
                kodilog(f"Unexpected Trakt activity row shape ignored: {string}")
    except Exception:
        pass
    return default_activities()


def set_activity(latest_activities):
    encoded = _encode_cache_value(latest_activities, "trakt_get_activity")
    if encoded is None:
        return
    dbcon = connect_database("trakt_db")
    dbcon.execute(TC_BASE_SET, ("trakt_get_activity", encoded))


def reset_activity(latest_activities):
    cached_data = get_activity()
    set_activity(latest_activities)
    return cached_data


def _decode_cache_value(raw_value, cache_key, expected_type, item_type=None):
    encoded_size = _encoded_cache_size(raw_value)
    if encoded_size is None:
        kodilog(f"Invalid Trakt cache row encoding ignored: {cache_key}")
        return None
    if encoded_size > MAX_TRAKT_JSON_ROW_SIZE:
        kodilog(f"Oversized or invalid Trakt cache row ignored: {cache_key}")
        return None

    decoded_from_json = False
    try:
        value = json.loads(raw_value)
        decoded_from_json = True
    except (
        UnicodeDecodeError,
        TypeError,
        ValueError,
        MemoryError,
        OverflowError,
        RecursionError,
    ):
        if encoded_size > MAX_TRAKT_LEGACY_LITERAL_SIZE:
            kodilog(f"Oversized legacy Trakt cache row ignored: {cache_key}")
            return None
        try:
            value = ast.literal_eval(raw_value)
        except (ValueError, SyntaxError, TypeError, MemoryError, OverflowError, RecursionError):
            kodilog(f"Corrupt Trakt cache row ignored: {cache_key}")
            return None

    if expected_type is tuple:
        valid = (
            isinstance(value, (list, tuple))
            and len(value) == 2
            and isinstance(value[0], list)
            and all(isinstance(item, dict) for item in value[0])
            and (value[1] is None or isinstance(value[1], dict))
        )
        if valid and decoded_from_json:
            value = (value[0], value[1])
    else:
        valid = isinstance(value, expected_type)
        if valid and item_type is not None:
            valid = all(isinstance(item, item_type) for item in value)
    if not valid:
        kodilog(f"Unexpected Trakt cache row type ignored: {cache_key}")
        return None
    return value


def _encoded_cache_size(raw_value):
    if isinstance(raw_value, bytes):
        return len(raw_value)
    if not isinstance(raw_value, str) or len(raw_value) > MAX_TRAKT_JSON_ROW_SIZE:
        return None if not isinstance(raw_value, str) else len(raw_value)
    try:
        return len(raw_value.encode("utf-8"))
    except UnicodeEncodeError:
        return None


def _encode_cache_value(value, cache_key):
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError, MemoryError, RecursionError):
        kodilog(f"Unsupported Trakt cache value not written: {cache_key}")
        return None
    if len(encoded) > MAX_TRAKT_JSON_ROW_SIZE:
        kodilog(f"Oversized Trakt cache value not written: {cache_key}")
        return None
    try:
        encoded_size = len(encoded.encode("utf-8"))
    except UnicodeEncodeError:
        kodilog(f"Invalid Trakt cache value encoding not written: {cache_key}")
        return None
    if encoded_size > MAX_TRAKT_JSON_ROW_SIZE:
        kodilog(f"Oversized Trakt cache value not written: {cache_key}")
        return None
    return encoded


def _matches_required_activity_shape(value, required):
    if not isinstance(value, dict):
        return False
    for key, required_value in required.items():
        if key not in value:
            return False
        actual_value = value[key]
        if isinstance(required_value, dict):
            if not _matches_required_activity_shape(actual_value, required_value):
                return False
        elif not isinstance(actual_value, type(required_value)):
            return False
    return True


def clear_trakt_hidden_data(list_type):
    string = f"trakt_hidden_items_{list_type}"
    try:
        dbcon = connect_database("trakt_db")
        dbcon.execute(DELETE, (string,))
    except Exception:
        pass


def clear_trakt_collection_watchlist_data(list_type, media_type):
    if media_type == "movies":
        media_type = "movie"
    if media_type in ("tvshows", "shows"):
        media_type = "tvshow"
    string = f"trakt_{list_type}_{media_type}"
    try:
        dbcon = connect_database("trakt_db")
        dbcon.execute(DELETE, (string,))
    except Exception:
        pass


def clear_trakt_list_contents_data(list_type):
    string = "trakt_list_contents_" + list_type + "_%"
    try:
        dbcon = connect_database("trakt_db")
        dbcon.execute(DELETE_LIKE % string)
    except Exception:
        pass


def clear_trakt_list_data(list_type):
    string = f"trakt_{list_type}"
    try:
        dbcon = connect_database("trakt_db")
        dbcon.execute(DELETE, (string,))
    except Exception:
        pass


def clear_trakt_calendar():
    try:
        dbcon = connect_database("trakt_db")
        dbcon.execute(DELETE_LIKE % "trakt_get_my_calendar_%")
    except Exception:
        return


def clear_trakt_recommendations():
    try:
        dbcon = connect_database("trakt_db")
        dbcon.execute(DELETE_LIKE % "trakt_recommendations_%")
    except Exception:
        return


def clear_trakt_favorites():
    try:
        dbcon = connect_database("trakt_db")
        dbcon.execute(DELETE_LIKE % "trakt_favorites_%")
    except Exception:
        return


def clear_trakt_watchlist():
    """
    Clear the cached Trakt.tv watchlist.
    """
    try:
        dbcon = connect_database("trakt_db")
        dbcon.execute(DELETE_LIKE % "trakt_watchlist_%")
    except Exception:
        pass


def default_activities():
    return {
        "all": "2024-01-22T00:22:21.000Z",
        "movies": {
            "watched_at": "2020-01-01T00:00:01.000Z",
            "collected_at": "2020-01-01T00:00:01.000Z",
            "rated_at": "2020-01-01T00:00:01.000Z",
            "watchlisted_at": "2020-01-01T00:00:01.000Z",
            "favorited_at": "2020-01-01T00:00:01.000Z",
            "recommendations_at": "2020-01-01T00:00:01.000Z",
            "commented_at": "2020-01-01T00:00:01.000Z",
            "paused_at": "2020-01-01T00:00:01.000Z",
            "hidden_at": "2020-01-01T00:00:01.000Z",
        },
        "episodes": {
            "watched_at": "2020-01-01T00:00:01.000Z",
            "collected_at": "2020-01-01T00:00:01.000Z",
            "rated_at": "2020-01-01T00:00:01.000Z",
            "watchlisted_at": "2020-01-01T00:00:01.000Z",
            "commented_at": "2020-01-01T00:00:01.000Z",
            "paused_at": "2020-01-01T00:00:01.000Z",
        },
        "shows": {
            "rated_at": "2020-01-01T00:00:01.000Z",
            "watchlisted_at": "2020-01-01T00:00:01.000Z",
            "favorited_at": "2020-01-01T00:00:01.000Z",
            "recommendations_at": "2020-01-01T00:00:01.000Z",
            "commented_at": "2020-01-01T00:00:01.000Z",
            "hidden_at": "2020-01-01T00:00:01.000Z",
        },
        "seasons": {
            "rated_at": "2020-01-01T00:00:01.000Z",
            "watchlisted_at": "2020-01-01T00:00:01.000Z",
            "commented_at": "2020-01-01T00:00:01.000Z",
            "hidden_at": "2020-01-01T00:00:01.000Z",
        },
        "comments": {
            "liked_at": "2020-01-01T00:00:01.000Z",
            "blocked_at": "2020-01-01T00:00:01.000Z",
        },
        "lists": {
            "liked_at": "2020-01-01T00:00:01.000Z",
            "updated_at": "2020-01-01T00:00:01.000Z",
            "commented_at": "2020-01-01T00:00:01.000Z",
        },
        "watchlist": {"updated_at": "2020-01-01T00:00:01.000Z"},
        "favorites": {"updated_at": "2020-01-01T00:00:01.000Z"},
        "recommendations": {"updated_at": "2020-01-01T00:00:01.000Z"},
        "collaborations": {"updated_at": "2020-01-01T00:00:01.000Z"},
        "account": {
            "settings_at": "2020-01-01T00:00:01.000Z",
            "followed_at": "2020-01-01T00:00:01.000Z",
            "following_at": "2020-01-01T00:00:01.000Z",
            "pending_at": "2020-01-01T00:00:01.000Z",
            "requested_at": "2020-01-01T00:00:01.000Z",
        },
        "saved_filters": {"updated_at": "2020-01-01T00:00:01.000Z"},
        "notes": {"updated_at": "2020-01-01T00:00:01.000Z"},
    }
