import base64
import contextlib
import math
import secrets
import time
from datetime import datetime

import requests
import xbmc
import xbmcgui

from lib.gui.qr_progress_dialog import QRProgressDialog
from lib.jacktook.utils import ADDON_PATH
from lib.utils.debrid.qrcode_utils import make_qrcode
from lib.utils.kodi.utils import get_setting, kodilog, notification, set_setting, translation

PROFILE_FETCH_AUTH = "auth"
PROFILE_FETCH_TRANSPORT = "transport"
PROFILE_FETCH_HTTP = "http"
PROFILE_FETCH_INVALID_JSON = "invalid_json"
PROFILE_FETCH_NON_LIST = "non_list"
PROFILE_FETCH_INVALID_ROWS = "invalid_rows"
ADDONS_FETCH_AUTH = "auth"
ADDONS_FETCH_TRANSPORT = "transport"
ADDONS_FETCH_HTTP = "http"
ADDONS_FETCH_INVALID_JSON = "invalid_json"
ADDONS_FETCH_NON_LIST = "non_list"
LIBRARY_RPC_CURSOR = "sync_get_library_delta_cursor"
LIBRARY_RPC_SNAPSHOT = "sync_pull_library"
LIBRARY_RPC_DELTA = "sync_pull_library_delta"
LIBRARY_RPC_PUSH_ITEMS = "sync_push_library_items"
LIBRARY_RPC_DELETE_ITEMS = "sync_delete_library_items"
WATCHED_RPC_PULL = "sync_pull_watched_items"
WATCHED_RPC_PUSH = "sync_push_watched_items"
WATCHED_RPC_DELETE = "sync_delete_watched_items"
COLLECTIONS_RPC_PULL = "sync_pull_collections"
LIBRARY_FETCH_AUTH = "auth"
LIBRARY_FETCH_TRANSPORT = "transport"
LIBRARY_FETCH_HTTP = "http"
LIBRARY_FETCH_INVALID_JSON = "invalid_json"
LIBRARY_FETCH_NON_LIST = "non_list"
LIBRARY_FETCH_INVALID_CURSOR = "invalid_cursor"
LIBRARY_WRITE_AUTH = "auth"
LIBRARY_WRITE_TRANSPORT = "transport"
LIBRARY_WRITE_HTTP = "http"
LIBRARY_WRITE_INVALID_INPUT = "invalid_input"
# Nuvio clients send at most 500 library items/keys per request.
LIBRARY_WRITE_BATCH_SIZE = 500

# Sentinel returned by _parse_library_row when a delta event carries an
# unrecognized operation. The caller must abort the whole batch so the cursor
# never advances past an event that could not be applied.
_LIBRARY_BATCH_ABORT = object()

# Sentinel returned by _library_rpc when the request itself failed. It is
# distinct from a parsed JSON null body, which callers must treat as an
# invalid/non-list payload rather than a transport failure.
_LIBRARY_RPC_FAILED = object()


class NuvioClient:
    BASE_URL = "https://api.nuvio.tv"
    PUBLISHABLE_KEY = "sb_publishable_1Clq8rlTVACkdcZuqr6_AD__xUUC_EN"
    REQUEST_TIMEOUT = 5
    REFRESH_LEEWAY_SECONDS = 60

    def __init__(
        self,
        access_token=None,
        refresh_token=None,
        expires_at=None,
        profile_id=None,
        request_timeout=None,
        deadline=None,
    ):
        access_token = get_setting("nuvio_access_token") if access_token is None else access_token
        refresh_token = (
            get_setting("nuvio_refresh_token") if refresh_token is None else refresh_token
        )
        self.access_token = str(access_token or "").strip()
        self.refresh_token = str(refresh_token or "").strip()
        self.expires_at = self._finite_number(
            get_setting("nuvio_expires_at") if expires_at is None else expires_at
        )
        self.profile_id = self._profile_index(
            get_setting("nuvio_profile_id") if profile_id is None else profile_id
        )
        self.request_timeout = self.REQUEST_TIMEOUT if request_timeout is None else request_timeout
        self.deadline = deadline
        self._last_token_failure_status = None

    def reload_session(self):
        """Refresh the session (tokens and selected profile) from settings.

        Long-lived callers such as the background sync service hold one client
        across cycles, so they must re-read the session to follow login,
        logout, token refresh, and profile switches without a restart.
        Returns the resolved profile index (or ``None`` when no profile is set).
        """
        self.access_token = str(get_setting("nuvio_access_token") or "").strip()
        self.refresh_token = str(get_setting("nuvio_refresh_token") or "").strip()
        self.expires_at = self._finite_number(get_setting("nuvio_expires_at"))
        self.profile_id = self._profile_index(get_setting("nuvio_profile_id"))
        return self.profile_id

    def _effective_request_timeout(self):
        """Per-request timeout, clamped to the optional wall-clock deadline.

        A deadline-bounded caller (the view sync) gets the smaller of its
        per-request cap and the time it has left, so no single request can
        outlast its budget.
        """
        if self.deadline is None:
            return self.request_timeout
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            return 0.001
        return min(self.request_timeout, remaining)

    @staticmethod
    def _finite_number(value):
        if isinstance(value, bool):
            return None
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        return parsed if math.isfinite(parsed) else None

    @classmethod
    def _positive_integer(cls, value):
        parsed = cls._finite_number(value)
        if parsed is None or parsed <= 0 or not parsed.is_integer():
            return None
        return int(parsed)

    @classmethod
    def _non_negative_integer(cls, value):
        parsed = cls._finite_number(value)
        if parsed is None or parsed < 0 or not parsed.is_integer():
            return None
        return int(parsed)

    @classmethod
    def _profile_index(cls, value):
        profile_id = cls._positive_integer(value)
        return profile_id if profile_id and profile_id <= 6 else None

    @property
    def _auth_headers(self):
        return {
            "Authorization": f"Bearer {self.access_token}",
            "apikey": self.PUBLISHABLE_KEY,
        }

    @property
    def _json_headers(self):
        return {"apikey": self.PUBLISHABLE_KEY, "Content-Type": "application/json"}

    @property
    def _device_login_headers(self):
        return {
            "apikey": self.PUBLISHABLE_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _persist_session(self):
        set_setting("nuvio_access_token", self.access_token)
        set_setting("nuvio_refresh_token", self.refresh_token)
        set_setting("nuvio_expires_at", str(int(self.expires_at)) if self.expires_at else "")
        set_setting("nuvio_authenticated", "true")

    def _clear_session(self):
        self.access_token = ""
        self.refresh_token = ""
        self.expires_at = None
        self.profile_id = None
        for setting_id, value in (
            ("nuvio_access_token", ""),
            ("nuvio_refresh_token", ""),
            ("nuvio_expires_at", ""),
            ("nuvio_authenticated", "false"),
            ("nuvio_profile_id", ""),
        ):
            set_setting(setting_id, value)

    def _apply_token_response(self, response_data, persist=True):
        if not isinstance(response_data, dict):
            return False
        access_token = str(response_data.get("access_token") or "").strip()
        if not access_token:
            return False
        refresh_token = response_data.get("refresh_token")
        if refresh_token is not None:
            self.refresh_token = str(refresh_token).strip()
        self.access_token = access_token
        expires_in = self._finite_number(response_data.get("expires_in"))
        self.expires_at = time.time() + expires_in if expires_in and expires_in > 0 else None
        if persist:
            self._persist_session()
        return True

    def _request_token(self, grant_type, payload):
        self._last_token_failure_status = None
        try:
            response = requests.post(
                f"{self.BASE_URL}/auth/v1/token?grant_type={grant_type}",
                headers=self._json_headers,
                json=payload,
                timeout=self._effective_request_timeout(),
            )
            if response.status_code >= 400:
                self._last_token_failure_status = response.status_code
                kodilog(f"[NUVIO] token request rejected (HTTP {response.status_code})")
                return None
            response_data = response.json()
        except (requests.RequestException, ValueError) as error:
            kodilog(f"[NUVIO] token request failed ({type(error).__name__})")
            return None
        return response_data if isinstance(response_data, dict) else None

    def refresh_access_token(self):
        if not self.refresh_token:
            return False
        response_data = self._request_token("refresh_token", {"refresh_token": self.refresh_token})
        return self._apply_token_response(response_data)

    def _ensure_access_token(self):
        if not self.access_token:
            return False
        if (
            self.expires_at is not None
            and time.time() >= self.expires_at - self.REFRESH_LEEWAY_SECONDS
        ):
            return self.refresh_access_token()
        return True

    def _post_authenticated(self, endpoint, payload=None, include_failure=False):
        def result(response, failure=None):
            return (response, failure) if include_failure else response

        if not self._ensure_access_token():
            return result(None, PROFILE_FETCH_AUTH)
        url = f"{self.BASE_URL}/rest/v1/rpc/{endpoint}"
        for attempt in range(2):
            try:
                request_args = {
                    "headers": self._auth_headers,
                    "timeout": self._effective_request_timeout(),
                }
                if payload is not None:
                    headers = dict(request_args["headers"])
                    headers["Content-Type"] = "application/json"
                    request_args["headers"] = headers
                    request_args["json"] = payload
                response = requests.post(url, **request_args)
            except requests.RequestException as error:
                kodilog(f"[NUVIO] {endpoint} transport failure ({type(error).__name__})")
                return result(None, PROFILE_FETCH_TRANSPORT)
            if response.status_code != 401 or attempt:
                return result(response)
            if not self.refresh_access_token():
                return result(None, PROFILE_FETCH_AUTH)
        return result(None, PROFILE_FETCH_AUTH)

    @staticmethod
    def _log_profile_fetch_failure(failure, status_code=None):
        status = f", HTTP {status_code}" if status_code is not None else ""
        kodilog(f"[NUVIO] profile fetch failed ({failure}{status})")

    def _fetch_profiles(self):
        response, failure = self._post_authenticated("sync_pull_profiles", include_failure=True)
        if failure:
            status_code = self._last_token_failure_status if failure == PROFILE_FETCH_AUTH else None
            self._log_profile_fetch_failure(failure, status_code)
            return None, failure
        if response.status_code >= 400:
            self._log_profile_fetch_failure(PROFILE_FETCH_HTTP, response.status_code)
            return None, PROFILE_FETCH_HTTP
        try:
            profiles = response.json()
        except ValueError:
            self._log_profile_fetch_failure(PROFILE_FETCH_INVALID_JSON)
            return None, PROFILE_FETCH_INVALID_JSON
        if not isinstance(profiles, list):
            self._log_profile_fetch_failure(PROFILE_FETCH_NON_LIST)
            return None, PROFILE_FETCH_NON_LIST
        if not profiles:
            return [], None
        available = {}
        for profile in profiles:
            if not isinstance(profile, dict):
                continue
            profile_id = self._profile_index(profile.get("profile_index"))
            if profile_id:
                available[profile_id] = profile
        if not available:
            self._log_profile_fetch_failure(PROFILE_FETCH_INVALID_ROWS)
            return None, PROFILE_FETCH_INVALID_ROWS
        return [available[index] for index in sorted(available)], None

    @staticmethod
    def _log_addons_fetch_failure(failure, status_code=None):
        status = f", HTTP {status_code}" if status_code is not None else ""
        kodilog(f"[NUVIO] addon list fetch failed ({failure}{status})")

    def get_addons(self):
        """Return valid enabled addon rows for the selected Nuvio profile.

        The remote URL values can contain private addon configuration, so this
        method deliberately logs only failure categories and never response data.
        """
        if not self.profile_id:
            self._log_addons_fetch_failure("invalid_profile")
            return None
        if not self._ensure_access_token():
            self._log_addons_fetch_failure(ADDONS_FETCH_AUTH, self._last_token_failure_status)
            return None

        params = {
            "select": "*",
            "profile_id": f"eq.{self.profile_id}",
            "order": "sort_order",
        }
        url = f"{self.BASE_URL}/rest/v1/addons"
        response = None
        for attempt in range(2):
            try:
                response = requests.get(
                    url,
                    params=params,
                    headers=self._auth_headers,
                    timeout=self._effective_request_timeout(),
                )
            except requests.RequestException as error:
                self._log_addons_fetch_failure(f"{ADDONS_FETCH_TRANSPORT}:{type(error).__name__}")
                return None
            if response.status_code != 401 or attempt:
                break
            if not self.refresh_access_token():
                self._log_addons_fetch_failure(ADDONS_FETCH_AUTH, self._last_token_failure_status)
                return None

        if response is None or response.status_code >= 400:
            self._log_addons_fetch_failure(
                ADDONS_FETCH_HTTP, response.status_code if response else None
            )
            return None
        try:
            rows = response.json()
        except ValueError:
            self._log_addons_fetch_failure(ADDONS_FETCH_INVALID_JSON)
            return None
        if not isinstance(rows, list):
            self._log_addons_fetch_failure(ADDONS_FETCH_NON_LIST)
            return None

        valid_rows = []
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            addon_url = row.get("url")
            name = row.get("name")
            sort_order = self._finite_number(row.get("sort_order"))
            if (
                not isinstance(addon_url, str)
                or not addon_url.strip()
                or (name is not None and not isinstance(name, str))
                or not isinstance(row.get("enabled"), bool)
                or sort_order is None
            ):
                continue
            if row["enabled"]:
                valid_rows.append(
                    {
                        "url": addon_url.strip(),
                        "name": name.strip() if isinstance(name, str) else "",
                        "enabled": True,
                        "sort_order": sort_order,
                        "_index": index,
                    }
                )
        valid_rows.sort(key=lambda row: (row["sort_order"], row["_index"]))
        for row in valid_rows:
            row.pop("_index", None)
        return valid_rows

    @staticmethod
    def _log_library_fetch_failure(label, failure, status_code=None):
        status = f", HTTP {status_code}" if status_code is not None else ""
        kodilog(f"[NUVIO] {label} fetch failed ({failure}{status})")

    @staticmethod
    def _log_library_write_failure(label, failure, status_code=None):
        status = f", HTTP {status_code}" if status_code is not None else ""
        kodilog(f"[NUVIO] {label} write failed ({failure}{status})")

    @staticmethod
    def _iter_batches(entries, size):
        for index in range(0, len(entries), size):
            yield entries[index : index + size]

    # API fields accepted by sync_push_library_items (Nuvio public API v1.3).
    LIBRARY_WRITE_FIELDS = (
        "content_id",
        "content_type",
        "name",
        "poster",
        "poster_shape",
        "background",
        "description",
        "release_info",
        "imdb_rating",
        "genres",
        "addon_base_url",
        "added_at",
    )

    @classmethod
    def _normalize_library_write_items(cls, items):
        """Return the validated API-shaped items to push, or None.

        Every item must carry a known ``content_type`` and a non-empty string
        ``content_id``. Only documented API fields are forwarded; local-only
        keys (``tmdb_id``, ``ids``, ``mode``, …) are stripped so they are never
        sent to the server.
        """
        if not isinstance(items, (list, tuple)) or not items:
            return None
        normalized = []
        for item in items:
            if not isinstance(item, dict):
                return None
            if item.get("content_type") not in ("movie", "series"):
                return None
            content_id = item.get("content_id")
            if not isinstance(content_id, str) or not content_id.strip():
                return None
            normalized.append(
                {field: item[field] for field in cls.LIBRARY_WRITE_FIELDS if field in item}
            )
        return normalized

    @classmethod
    def _normalize_library_write_keys(cls, keys):
        """Return validated ``{"content_id", "content_type"}`` keys, or None."""
        if not isinstance(keys, (list, tuple)) or not keys:
            return None
        normalized = []
        for key in keys:
            if not isinstance(key, dict):
                return None
            content_type = key.get("content_type")
            content_id = key.get("content_id")
            if content_type not in ("movie", "series"):
                return None
            if not isinstance(content_id, str) or not content_id.strip():
                return None
            normalized.append({"content_id": content_id, "content_type": content_type})
        return normalized

    @classmethod
    def _normalize_watched_write_items(cls, items):
        """Return validated watched-history items, or None.

        Every item must carry a non-empty string ``content_id``, a known
        ``content_type``, and a positive integer ``watched_at`` (epoch ms).
        Only documented API fields are forwarded; local-only keys such as
        ``tmdb_id`` or ``mode`` are stripped. ``season``/``episode`` are only
        forwarded for series and must be supplied together.
        """
        if not isinstance(items, (list, tuple)) or not items:
            return None
        normalized = []
        for item in items:
            if not isinstance(item, dict):
                return None
            content_type = item.get("content_type")
            content_id = item.get("content_id")
            if content_type not in ("movie", "series"):
                return None
            if not isinstance(content_id, str) or not content_id.strip():
                return None
            watched_at = cls._positive_integer(item.get("watched_at"))
            if watched_at is None:
                return None
            entry = {
                "content_id": content_id.strip(),
                "content_type": content_type,
                "watched_at": watched_at,
            }
            title = item.get("title")
            if isinstance(title, str) and title.strip():
                entry["title"] = title.strip()
            if content_type == "series" and (
                item.get("season") is not None or item.get("episode") is not None
            ):
                season = cls._non_negative_integer(item.get("season"))
                episode = cls._positive_integer(item.get("episode"))
                if season is None or episode is None:
                    return None
                entry["season"] = season
                entry["episode"] = episode
            normalized.append(entry)
        return normalized

    @classmethod
    def _normalize_watched_write_keys(cls, keys):
        """Return validated ``{"content_id", "season"?, "episode"?}`` keys, or None.

        Season and episode are optional (movies omit both) but must be supplied
        together when present, mirroring the API requirement for series episodes.
        """
        if not isinstance(keys, (list, tuple)) or not keys:
            return None
        normalized = []
        for key in keys:
            if not isinstance(key, dict):
                return None
            content_id = key.get("content_id")
            if not isinstance(content_id, str) or not content_id.strip():
                return None
            entry = {"content_id": content_id.strip()}
            if key.get("season") is not None or key.get("episode") is not None:
                season = cls._non_negative_integer(key.get("season"))
                episode = cls._positive_integer(key.get("episode"))
                if season is None or episode is None:
                    return None
                entry["season"] = season
                entry["episode"] = episode
            normalized.append(entry)
        return normalized

    def _library_write(self, endpoint, payload, label):
        """Run one incremental library write RPC; return True on 2xx/3xx.

        Responses are ``204 No Content``, so the body is never parsed. Failures
        are reported by category only, response data is never logged, and no
        exception escapes to the caller.
        """
        try:
            response, failure = self._post_authenticated(endpoint, payload, include_failure=True)
        except Exception as error:
            self._log_library_write_failure(label, f"unexpected:{type(error).__name__}")
            return False
        if failure:
            status_code = self._last_token_failure_status if failure == LIBRARY_WRITE_AUTH else None
            self._log_library_write_failure(label, failure, status_code)
            return False
        if response is None or response.status_code >= 400:
            self._log_library_write_failure(
                label, LIBRARY_WRITE_HTTP, response.status_code if response else None
            )
            return False
        return True

    def _library_profile_id(self, profile_id):
        if profile_id is None:
            return self.profile_id
        return self._profile_index(profile_id)

    def _library_rpc(self, endpoint, payload, label):
        """Run a read-only library RPC and return parsed JSON or a sentinel.

        Failures are reported by category only and return
        ``_LIBRARY_RPC_FAILED``; response data is never logged.
        """
        response, failure = self._post_authenticated(endpoint, payload, include_failure=True)
        if failure:
            status_code = self._last_token_failure_status if failure == LIBRARY_FETCH_AUTH else None
            self._log_library_fetch_failure(label, failure, status_code)
            return _LIBRARY_RPC_FAILED
        if response is None or response.status_code >= 400:
            self._log_library_fetch_failure(
                label, LIBRARY_FETCH_HTTP, response.status_code if response else None
            )
            return _LIBRARY_RPC_FAILED
        try:
            return response.json()
        except ValueError:
            self._log_library_fetch_failure(label, LIBRARY_FETCH_INVALID_JSON)
            return _LIBRARY_RPC_FAILED

    @classmethod
    def _clamp_library_limit(cls, value, default):
        parsed = cls._non_negative_integer(value)
        if parsed is None:
            return default
        return max(1, min(parsed, 1000))

    @staticmethod
    def _optional_string(value):
        return value.strip() if isinstance(value, str) else ""

    @staticmethod
    def _string_list(value):
        if not isinstance(value, list):
            return []
        return [entry.strip() for entry in value if isinstance(entry, str) and entry.strip()]

    @classmethod
    def _parse_library_row(cls, row, include_event=False):
        """Normalize a library row; return None to skip or the abort sentinel.

        Identity must be a positive ``tmdb:`` content id with a known
        ``content_type``. Delta rows must carry a recognized ``operation``;
        any other value aborts the whole batch so the cursor cannot skip it.
        """
        if not isinstance(row, dict):
            return None
        if include_event and row.get("operation") not in ("upsert", "delete"):
            return _LIBRARY_BATCH_ABORT
        content_type = row.get("content_type")
        if content_type not in ("movie", "series"):
            return None
        content_id = row.get("content_id")
        tmdb_id = cls._tmdb_id_from_content_id(content_id)
        if not tmdb_id:
            return None
        parsed = {
            "content_type": content_type,
            "content_id": content_id.strip(),
            "tmdb_id": tmdb_id,
            "title": cls._optional_string(row.get("name")),
            "poster": cls._optional_string(row.get("poster")),
            "background": cls._optional_string(row.get("background")),
            "description": cls._optional_string(row.get("description")),
            "release_info": cls._optional_string(row.get("release_info")),
            "imdb_rating": cls._finite_number(row.get("imdb_rating")),
            "genres": cls._string_list(row.get("genres")),
            "addon_base_url": cls._optional_string(row.get("addon_base_url")),
            "added_at_ms": cls._non_negative_integer(row.get("added_at")) or 0,
        }
        if include_event:
            event_id = cls._positive_integer(row.get("event_id"))
            if event_id is None:
                return None
            parsed["event_id"] = event_id
            parsed["operation"] = row["operation"]
        return parsed

    def get_library_delta_cursor(self, profile_id=None):
        """Return the highest library event id for the profile, or None.

        The RPC responds with a bare JSON integer; ``0`` is a valid cursor.
        """
        resolved_profile = self._library_profile_id(profile_id)
        if not resolved_profile:
            self._log_library_fetch_failure("library cursor", "invalid_profile")
            return None
        data = self._library_rpc(
            LIBRARY_RPC_CURSOR, {"p_profile_id": resolved_profile}, "library cursor"
        )
        if data is _LIBRARY_RPC_FAILED:
            return None
        if isinstance(data, bool) or not isinstance(data, int):
            self._log_library_fetch_failure("library cursor", LIBRARY_FETCH_INVALID_CURSOR)
            return None
        return data

    def _pull_library_page(self, endpoint, payload, label, include_event=False):
        """Run one read-only page RPC; return (items, raw_row_count) or None.

        The raw row count is returned alongside the parsed items so callers can
        apply the documented "stop when the page is shorter than the limit" rule
        against the server's actual page size, not the count of rows that
        survived parsing.
        """
        data = self._library_rpc(endpoint, payload, label)
        if data is _LIBRARY_RPC_FAILED:
            return None
        if not isinstance(data, list):
            self._log_library_fetch_failure(label, LIBRARY_FETCH_NON_LIST)
            return None
        items = []
        for row in data:
            parsed = self._parse_library_row(row, include_event=include_event)
            if parsed is _LIBRARY_BATCH_ABORT:
                self._log_library_fetch_failure(label, "invalid_operation")
                return None
            if parsed is None:
                continue
            items.append(parsed)
        if include_event:
            items.sort(key=lambda event: event["event_id"])
        return items, len(data)

    def get_library_page(self, profile_id=None, limit=500, offset=0):
        """Pull one snapshot page; return ``(items, raw_row_count)`` or None."""
        resolved_profile = self._library_profile_id(profile_id)
        if not resolved_profile:
            self._log_library_fetch_failure("library snapshot", "invalid_profile")
            return None
        page_limit = self._non_negative_integer(limit)
        page_offset = self._non_negative_integer(offset)
        return self._pull_library_page(
            LIBRARY_RPC_SNAPSHOT,
            {
                "p_profile_id": resolved_profile,
                "p_limit": 500 if page_limit is None else page_limit,
                "p_offset": 0 if page_offset is None else page_offset,
            },
            "library snapshot",
            include_event=False,
        )

    def get_library(self, profile_id=None, limit=500, offset=0):
        """Pull one snapshot page of the profile library, or None on failure."""
        page = self.get_library_page(profile_id=profile_id, limit=limit, offset=offset)
        return None if page is None else page[0]

    def get_library_delta_page(self, profile_id=None, since_event_id=0, limit=1000):
        """Pull one delta page; return ``(events, raw_row_count)`` or None.

        An unrecognized ``operation`` aborts the batch (returns None) so the
        cursor never advances past an event that could not be applied.
        """
        resolved_profile = self._library_profile_id(profile_id)
        if not resolved_profile:
            self._log_library_fetch_failure("library delta", "invalid_profile")
            return None
        since = self._non_negative_integer(since_event_id)
        return self._pull_library_page(
            LIBRARY_RPC_DELTA,
            {
                "p_profile_id": resolved_profile,
                "p_since_event_id": 0 if since is None else since,
                "p_limit": self._clamp_library_limit(limit, 1000),
            },
            "library delta",
            include_event=True,
        )

    def get_library_delta(self, profile_id=None, since_event_id=0, limit=1000):
        """Pull library change events since a cursor, ordered by event id.

        An unrecognized ``operation`` aborts the batch (returns None) so the
        cursor never advances past an event that could not be applied.
        """
        page = self.get_library_delta_page(
            profile_id=profile_id,
            since_event_id=since_event_id,
            limit=limit,
        )
        return None if page is None else page[0]

    def add_library_items(self, profile_id=None, items=None, origin_client_id=None) -> bool:
        """Incrementally upsert library items for the profile.

        Uses only ``sync_push_library_items`` (never the destructive full
        replace). Items are chunked to the documented 500-per-request client
        limit; any failed chunk makes the whole call return ``False``.
        """
        resolved_profile = self._library_profile_id(profile_id)
        if not resolved_profile:
            self._log_library_write_failure("library push", LIBRARY_WRITE_INVALID_INPUT)
            return False
        normalized = self._normalize_library_write_items(items)
        if not normalized:
            self._log_library_write_failure("library push", LIBRARY_WRITE_INVALID_INPUT)
            return False
        origin = self._optional_string(origin_client_id) or None
        for batch in self._iter_batches(normalized, LIBRARY_WRITE_BATCH_SIZE):
            payload = {
                "p_profile_id": resolved_profile,
                "p_items": batch,
                "p_origin_client_id": origin,
            }
            if not self._library_write(LIBRARY_RPC_PUSH_ITEMS, payload, "library push"):
                return False
        return True

    def remove_library_items(self, profile_id=None, keys=None, origin_client_id=None) -> bool:
        """Incrementally delete explicit ``(content_id, content_type)`` keys.

        Uses only ``sync_delete_library_items`` (never the destructive full
        replace). Keys are chunked to the documented 500-per-request limit.
        """
        resolved_profile = self._library_profile_id(profile_id)
        if not resolved_profile:
            self._log_library_write_failure("library delete", LIBRARY_WRITE_INVALID_INPUT)
            return False
        normalized = self._normalize_library_write_keys(keys)
        if not normalized:
            self._log_library_write_failure("library delete", LIBRARY_WRITE_INVALID_INPUT)
            return False
        origin = self._optional_string(origin_client_id) or None
        for batch in self._iter_batches(normalized, LIBRARY_WRITE_BATCH_SIZE):
            payload = {
                "p_profile_id": resolved_profile,
                "p_keys": batch,
                "p_origin_client_id": origin,
            }
            if not self._library_write(LIBRARY_RPC_DELETE_ITEMS, payload, "library delete"):
                return False
        return True

    def push_watched_items(self, profile_id=None, items=None) -> bool:
        """Upsert watched-history items for the profile.

        Uses only ``sync_push_watched_items`` (a non-destructive merge). The
        response is ``204 No Content``, so the body is never parsed. Invalid or
        empty input is rejected before any request is made.
        """
        resolved_profile = self._library_profile_id(profile_id)
        if not resolved_profile:
            self._log_library_write_failure("watched push", LIBRARY_WRITE_INVALID_INPUT)
            return False
        normalized = self._normalize_watched_write_items(items)
        if not normalized:
            self._log_library_write_failure("watched push", LIBRARY_WRITE_INVALID_INPUT)
            return False
        payload = {"p_profile_id": resolved_profile, "p_items": normalized}
        return self._library_write(WATCHED_RPC_PUSH, payload, "watched push")

    def delete_watched_items(self, profile_id=None, keys=None) -> bool:
        """Delete explicit watched-history keys for the profile.

        Uses only ``sync_delete_watched_items``. The response is
        ``204 No Content``, so the body is never parsed. Invalid or empty input
        is rejected before any request is made.
        """
        resolved_profile = self._library_profile_id(profile_id)
        if not resolved_profile:
            self._log_library_write_failure("watched delete", LIBRARY_WRITE_INVALID_INPUT)
            return False
        normalized = self._normalize_watched_write_keys(keys)
        if not normalized:
            self._log_library_write_failure("watched delete", LIBRARY_WRITE_INVALID_INPUT)
            return False
        payload = {"p_profile_id": resolved_profile, "p_keys": normalized}
        return self._library_write(WATCHED_RPC_DELETE, payload, "watched delete")

    @staticmethod
    def _device_nonce():
        return base64.urlsafe_b64encode(secrets.token_bytes(24)).rstrip(b"=").decode("ascii")

    @staticmethod
    def _first_device_login_row(response_data, required_fields):
        if not isinstance(response_data, list) or not response_data:
            return None
        row = response_data[0]
        if not isinstance(row, dict):
            return None
        if any(
            not isinstance(row.get(field), str) or not row[field].strip()
            for field in required_fields
        ):
            return None
        return row

    @classmethod
    def _device_poll_interval(cls, value, default=None):
        interval = cls._finite_number(value)
        if interval is None or interval <= 0:
            return default
        return max(interval, 2)

    @staticmethod
    def _device_login_deadline(expires_at):
        if not isinstance(expires_at, str) or not expires_at.strip():
            return None
        try:
            parsed = datetime.fromisoformat(expires_at.strip().replace("Z", "+00:00"))
            return time.monotonic() + max(parsed.timestamp() - time.time(), 0)
        except (TypeError, ValueError, OverflowError):
            return None

    @staticmethod
    def _is_missing_device_login_function(response):
        try:
            response_data = response.json()
        except ValueError:
            return False
        if not isinstance(response_data, dict):
            return False
        message = " ".join(
            str(response_data.get(field) or "") for field in ("message", "details", "hint")
        ).lower()
        return "could not find the function" in message and "start_device_login_session" in message

    def _post_device_login(self, endpoint, payload):
        try:
            response = requests.post(
                f"{self.BASE_URL}{endpoint}",
                headers=self._device_login_headers,
                json=payload,
                timeout=self._effective_request_timeout(),
            )
        except requests.RequestException as error:
            kodilog(
                f"[NUVIO] device login {endpoint.rsplit('/', 1)[-1]} "
                f"transport failure ({type(error).__name__})"
            )
            return None
        return response

    def _start_device_login(self, nonce):
        response = self._post_device_login(
            "/rest/v1/rpc/start_device_login_session",
            {
                "p_device_nonce": nonce,
                "p_redirect_base_url": "https://nuvio.tv/link",
                "p_device_type": "tv",
            },
        )
        if response is None:
            return None
        if response.status_code >= 400:
            if self._is_missing_device_login_function(response):
                return self._start_legacy_device_login(nonce)
            kodilog(f"[NUVIO] device login start rejected (HTTP {response.status_code})")
            return None
        try:
            response_data = response.json()
        except ValueError:
            kodilog("[NUVIO] device login start invalid_json")
            return None
        row = self._first_device_login_row(
            response_data,
            (
                "device_code",
                "user_code",
                "verification_uri",
                "verification_uri_complete",
                "expires_at",
            ),
        )
        if row is None or self._device_poll_interval(row.get("poll_interval_seconds")) is None:
            kodilog("[NUVIO] device login start invalid_response")
            return None
        return row

    def _start_legacy_device_login(self, nonce):
        response = self._post_device_login(
            "/rest/v1/rpc/start_tv_login_session",
            {"p_device_nonce": nonce, "p_redirect_base_url": "https://nuvio.tv"},
        )
        if response is None:
            return None
        if response.status_code >= 400:
            kodilog(f"[NUVIO] legacy device login start rejected (HTTP {response.status_code})")
            return None
        try:
            response_data = response.json()
        except ValueError:
            kodilog("[NUVIO] legacy device login start invalid_json")
            return None
        row = self._first_device_login_row(response_data, ("code", "web_url", "expires_at"))
        if row is None or self._device_poll_interval(row.get("poll_interval_seconds")) is None:
            kodilog("[NUVIO] legacy device login start invalid_response")
            return None
        return {
            "device_code": row["code"],
            "user_code": row["code"],
            "verification_uri": "https://nuvio.tv",
            "verification_uri_complete": row["web_url"],
            "expires_at": row["expires_at"],
            "poll_interval_seconds": row["poll_interval_seconds"],
        }

    def _poll_device_login(self, device_code, nonce):
        response = self._post_device_login(
            "/rest/v1/rpc/poll_tv_login_session",
            {"p_code": device_code, "p_device_nonce": nonce},
        )
        if response is None:
            return None
        if response.status_code >= 400:
            kodilog(f"[NUVIO] device login poll rejected (HTTP {response.status_code})")
            return None
        try:
            response_data = response.json()
        except ValueError:
            kodilog("[NUVIO] device login poll invalid_json")
            return None
        row = self._first_device_login_row(response_data, ("status",))
        if row is None:
            kodilog("[NUVIO] device login poll invalid_response")
        return row

    def _exchange_device_login(self, device_code, nonce):
        response = self._post_device_login(
            "/functions/v1/tv-logins-exchange",
            {"code": device_code, "device_nonce": nonce},
        )
        if response is None:
            return False
        if response.status_code >= 400:
            kodilog(f"[NUVIO] device login exchange rejected (HTTP {response.status_code})")
            return False
        try:
            response_data = response.json()
        except ValueError:
            kodilog("[NUVIO] device login exchange invalid_json")
            return False
        if not isinstance(response_data, dict) or not all(
            isinstance(response_data.get(field), str) and response_data[field].strip()
            for field in ("access_token", "refresh_token")
        ):
            kodilog("[NUVIO] device login exchange invalid_response")
            return False
        return self._apply_token_response(response_data, persist=False)

    @staticmethod
    def _wait_for_device_poll(delay, progress_dialog, monitor):
        wait_deadline = time.monotonic() + delay
        while True:
            if progress_dialog.iscanceled or monitor.abortRequested():
                return False
            remaining = wait_deadline - time.monotonic()
            if remaining <= 0:
                return True
            if monitor.waitForAbort(min(remaining, 0.25)):
                return False

    def _select_profile_after_login(self):
        dialog = xbmcgui.Dialog()
        profiles, failure = self._fetch_profiles()
        if failure:
            self._clear_session()
            dialog.ok("Nuvio", translation(91015))
            return False
        if not profiles:
            self.profile_id = 1
            self._persist_session()
            set_setting("nuvio_profile_id", str(self.profile_id))
            kodilog("[NUVIO] remote profiles empty; selected local Profile 1")
            notification(translation(91016), time=3000)
            return True
        labels = [
            f"{profile['profile_index']}: {str(profile.get('name') or 'Profile').strip()}"
            for profile in profiles
        ]
        selected = dialog.select(translation(91017), labels)
        if not isinstance(selected, int) or selected < 0 or selected >= len(profiles):
            self._clear_session()
            notification(translation(91009), time=3000)
            return False

        self.profile_id = self._profile_index(profiles[selected].get("profile_index"))
        if not self.profile_id:
            self._clear_session()
            return False
        self._persist_session()
        set_setting("nuvio_profile_id", str(self.profile_id))
        notification(translation(91016), time=3000)
        return True

    def authenticate(self):
        nonce = self._device_nonce()
        device_login = self._start_device_login(nonce)
        if not device_login:
            notification(translation(91012), time=5000)
            return False

        interval = self._device_poll_interval(device_login["poll_interval_seconds"])
        deadline = self._device_login_deadline(device_login["expires_at"])
        started_at = time.monotonic()
        expires_in = max(deadline - started_at, 1) if deadline is not None else None
        progress_dialog = QRProgressDialog("qr_dialog.xml", ADDON_PATH)
        monitor = xbmc.Monitor()
        try:
            progress_dialog.setup(
                translation(90558),
                make_qrcode(device_login["verification_uri_complete"]),
                device_login["verification_uri"],
                device_login["user_code"],
                "",
                is_debrid=False,
            )
            progress_dialog.show_dialog()
            while True:
                if progress_dialog.iscanceled or monitor.abortRequested():
                    kodilog("[NUVIO] device login cancelled")
                    notification(translation(91009), time=3000)
                    return False
                remaining = deadline - time.monotonic() if deadline is not None else None
                if remaining is not None and remaining <= 0:
                    kodilog("[NUVIO] device login expired")
                    notification(translation(91010), time=5000)
                    return False
                if not self._wait_for_device_poll(
                    min(interval, remaining) if remaining is not None else interval,
                    progress_dialog,
                    monitor,
                ):
                    kodilog("[NUVIO] device login cancelled")
                    notification(translation(91009), time=3000)
                    return False
                if deadline is not None and time.monotonic() >= deadline:
                    kodilog("[NUVIO] device login expired")
                    notification(translation(91010), time=5000)
                    return False

                poll_result = self._poll_device_login(device_login["device_code"], nonce)
                if poll_result is None:
                    notification(translation(91013), time=5000)
                    return False
                interval = self._device_poll_interval(
                    poll_result.get("poll_interval_seconds"), interval
                )
                poll_deadline = self._device_login_deadline(poll_result.get("expires_at"))
                if poll_deadline is not None:
                    deadline = poll_deadline
                if expires_in is not None:
                    elapsed = max(time.monotonic() - started_at, 0)
                    progress_dialog.update_progress(min(int(100 * elapsed / expires_in), 99))

                status = poll_result["status"].strip().lower()
                if status == "approved":
                    if not self._exchange_device_login(device_login["device_code"], nonce):
                        notification(translation(91014), time=5000)
                        return False
                    return self._select_profile_after_login()
                if status in ("expired", "used", "cancelled"):
                    kodilog(f"[NUVIO] device login terminal status={status}")
                    notification(translation(91010 if status == "expired" else 91011), time=5000)
                    return False
        finally:
            with contextlib.suppress(BaseException):
                progress_dialog.close_dialog()

    @classmethod
    def progress_payload(cls, data, now_ms=None):
        if not isinstance(data, dict):
            return None
        ids = data.get("ids")
        tmdb_id = cls._positive_integer(ids.get("tmdb_id")) if isinstance(ids, dict) else None
        if not tmdb_id:
            return None
        position_seconds = cls._finite_number(data.get("current_time"))
        duration_seconds = cls._finite_number(data.get("total_time"))
        if (
            position_seconds is None
            or duration_seconds is None
            or position_seconds < 0
            or duration_seconds <= 0
        ):
            return None
        position = int(min(position_seconds, duration_seconds) * 1000)
        duration = int(duration_seconds * 1000)
        if duration <= 0:
            return None
        content_id = f"tmdb:{tmdb_id}"
        entry = {
            "content_id": content_id,
            "position": position,
            "duration": duration,
            "last_watched": int(time.time() * 1000) if now_ms is None else int(now_ms),
        }
        if data.get("mode") == "movies":
            entry.update({"content_type": "movie", "video_id": content_id})
            return entry
        if data.get("mode") != "tv":
            return None
        tv_data = data.get("tv_data")
        if not isinstance(tv_data, dict):
            return None
        season = cls._non_negative_integer(tv_data.get("season"))
        episode = cls._positive_integer(tv_data.get("episode"))
        if season is None or not episode:
            return None
        entry.update(
            {
                "content_type": "series",
                "video_id": f"{content_id}:{season}:{episode}",
                "season": season,
                "episode": episode,
            }
        )
        return entry

    def push_watch_progress(self, data):
        entry = self.progress_payload(data)
        if entry is None or not self.profile_id:
            return False
        response = self._post_authenticated(
            "sync_push_watch_progress",
            {"p_profile_id": self.profile_id, "p_entries": [entry]},
        )
        if response is None or response.status_code >= 400:
            if response is not None:
                kodilog(f"[NUVIO] watch-progress push rejected (HTTP {response.status_code})")
            return False
        return True

    @staticmethod
    def _tmdb_id_from_content_id(content_id):
        """Parse "tmdb:550" into 550; return None for anything else."""
        if not isinstance(content_id, str):
            return None
        prefix, _, raw_id = content_id.strip().partition(":")
        if prefix.lower() != "tmdb":
            return None
        try:
            tmdb_id = int(raw_id.strip())
        except ValueError:
            return None
        return tmdb_id if tmdb_id > 0 else None

    def get_watch_progress(self, limit=200):
        """Pull remote watch-progress entries for the selected Nuvio profile."""
        if not self.profile_id:
            kodilog("[NUVIO] watch-progress pull failed (invalid_profile)")
            return []
        response = self._post_authenticated(
            "sync_pull_watch_progress",
            {
                "p_profile_id": self.profile_id,
                "p_since_last_watched": None,
                "p_limit": limit,
            },
        )
        if response is None or response.status_code >= 400:
            status = response.status_code if response is not None else None
            kodilog(f"[NUVIO] watch-progress pull failed (HTTP {status})")
            return []
        try:
            entries = response.json()
        except ValueError:
            kodilog("[NUVIO] watch-progress pull failed (invalid_json)")
            return []
        if not isinstance(entries, list):
            kodilog("[NUVIO] watch-progress pull failed (non_list)")
            return []

        items = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            tmdb_id = self._tmdb_id_from_content_id(entry.get("content_id"))
            if not tmdb_id:
                continue
            content_type = entry.get("content_type")
            if content_type not in ("movie", "series"):
                continue
            duration_ms = self._non_negative_integer(entry.get("duration"))
            if not duration_ms:
                continue
            position_ms = self._non_negative_integer(entry.get("position"))
            if position_ms is None:
                position_ms = 0
            last_watched_ms = self._non_negative_integer(entry.get("last_watched"))
            if last_watched_ms is None:
                continue
            season = episode = None
            if content_type == "series":
                season = self._non_negative_integer(entry.get("season"))
                episode = self._positive_integer(entry.get("episode"))
                if season is None or not episode:
                    continue
            progress_key = str(entry.get("progress_key") or "").strip()
            if not progress_key:
                continue
            items.append(
                {
                    "tmdb_id": tmdb_id,
                    "mode": "tv" if content_type == "series" else "movies",
                    "season": season,
                    "episode": episode,
                    "position_ms": position_ms,
                    "duration_ms": duration_ms,
                    "percent": round(min(position_ms / duration_ms * 100, 100.0), 2),
                    "last_watched_ms": last_watched_ms,
                    "progress_key": progress_key,
                }
            )
        return items

    def delete_watch_progress(self, progress_key):
        """Delete a single remote watch-progress entry for the selected profile."""
        progress_key = str(progress_key or "").strip()
        if not progress_key:
            kodilog("[NUVIO] watch-progress delete failed (invalid_progress_key)")
            return False
        if not self.profile_id:
            kodilog("[NUVIO] watch-progress delete failed (invalid_profile)")
            return False
        response = self._post_authenticated(
            "sync_delete_watch_progress",
            {"p_progress_key": progress_key, "p_profile_id": self.profile_id},
        )
        if response is None or response.status_code >= 400:
            if response is not None:
                kodilog(f"[NUVIO] watch-progress delete rejected (HTTP {response.status_code})")
            return False
        return True

    def get_watched_history_page(self, page=1, page_size=500):
        """Pull one page of watched history; return ``(items, raw_row_count)``.

        Returns ``None`` when the request or payload failed. The raw row count
        is returned alongside the parsed items so callers can apply the "stop
        when the page is shorter than the limit" rule against the server's
        actual page size, not the count of rows that survived parsing.
        """
        if not self.profile_id:
            kodilog("[NUVIO] watched-history pull failed (invalid_profile)")
            return None
        response = self._post_authenticated(
            WATCHED_RPC_PULL,
            {
                "p_profile_id": self.profile_id,
                "p_page": page,
                "p_page_size": page_size,
            },
        )
        if response is None or response.status_code >= 400:
            status = response.status_code if response is not None else None
            kodilog(f"[NUVIO] watched-history pull failed (HTTP {status})")
            return None
        try:
            rows = response.json()
        except ValueError:
            kodilog("[NUVIO] watched-history pull failed (invalid_json)")
            return None
        if not isinstance(rows, list):
            kodilog("[NUVIO] watched-history pull failed (non_list)")
            return None

        items = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            tmdb_id = self._tmdb_id_from_content_id(row.get("content_id"))
            if not tmdb_id:
                continue
            content_type = row.get("content_type")
            if content_type not in ("movie", "series"):
                continue
            title = row.get("title")
            title = title.strip() if isinstance(title, str) else ""
            watched_at_ms = self._non_negative_integer(row.get("watched_at"))
            if watched_at_ms is None:
                continue
            season = episode = None
            if content_type == "series":
                season = self._non_negative_integer(row.get("season"))
                episode = self._positive_integer(row.get("episode"))
                if season is None or not episode:
                    continue
            items.append(
                {
                    "tmdb_id": tmdb_id,
                    "mode": "tv" if content_type == "series" else "movies",
                    "season": season,
                    "episode": episode,
                    "title": title,
                    "watched_at_ms": watched_at_ms,
                }
            )
        return items, len(rows)

    def get_collections(self, profile_id=None):
        """Pull the profile's collections, or None on failure.

        Returns a normalized list of collections. Failure is ``None`` and a real
        empty collection set is ``[]`` so the caller can tell them apart. Only
        failure categories are logged; response data is never logged.
        """
        resolved_profile = self._library_profile_id(profile_id)
        if not resolved_profile:
            self._log_library_fetch_failure("collections", "invalid_profile")
            return None
        data = self._library_rpc(
            COLLECTIONS_RPC_PULL, {"p_profile_id": resolved_profile}, "collections"
        )
        if data is _LIBRARY_RPC_FAILED:
            return None
        if not isinstance(data, list):
            self._log_library_fetch_failure("collections", LIBRARY_FETCH_NON_LIST)
            return None
        collections = []
        for row in data:
            if not isinstance(row, dict):
                continue
            raw_collections = row.get("collections_json")
            if not isinstance(raw_collections, list):
                continue
            for entry in raw_collections:
                normalized = self._normalize_collection(entry)
                if normalized is not None:
                    collections.append(normalized)
        return collections

    @staticmethod
    def _normalize_collection(entry):
        """Normalize one collection object; ``None`` when it has no usable id."""
        if not isinstance(entry, dict):
            return None
        collection_id = NuvioClient._optional_string(entry.get("id"))
        if not collection_id:
            return None
        folders = []
        raw_folders = entry.get("folders")
        if isinstance(raw_folders, list):
            for folder in raw_folders:
                normalized = NuvioClient._normalize_collection_folder(folder)
                if normalized is not None:
                    folders.append(normalized)
        return {
            "id": collection_id,
            "title": NuvioClient._optional_string(entry.get("title")),
            "backdrop": NuvioClient._optional_string(entry.get("backdropImageUrl")),
            "view_mode": NuvioClient._optional_string(entry.get("viewMode")),
            "folders": folders,
        }

    @staticmethod
    def _normalize_collection_folder(folder):
        """Normalize one folder object; ``None`` when it has no usable id."""
        if not isinstance(folder, dict):
            return None
        folder_id = NuvioClient._optional_string(folder.get("id"))
        if not folder_id:
            return None
        raw_sources = folder.get("sources")
        if not isinstance(raw_sources, list):
            raw_sources = folder.get("catalogSources")
        sources = []
        if isinstance(raw_sources, list):
            for source in raw_sources:
                normalized = NuvioClient._normalize_collection_source(source)
                if normalized is not None:
                    sources.append(normalized)
        return {
            "id": folder_id,
            "title": NuvioClient._optional_string(folder.get("title")),
            "cover": NuvioClient._optional_string(folder.get("coverImageUrl")),
            "emoji": NuvioClient._optional_string(folder.get("coverEmoji")),
            "sources": sources,
        }

    @staticmethod
    def _normalize_collection_source(source):
        """Normalize one source object; ``None`` only for non-dict entries.

        Two source families coexist. Catalog sources carry both ``type`` and
        ``catalogId`` and are routed to the existing addon catalog viewer.
        TMDB discover sources carry a provider of tmdb (and/or a filters dict)
        and are routed to the discover view. Anything else is kept as unknown
        so the UI can surface an unsupported notice instead of silently
        dropping the source.
        """
        if not isinstance(source, dict):
            return None
        source_type = NuvioClient._optional_string(source.get("type"))
        catalog_id = NuvioClient._optional_string(source.get("catalogId"))

        label = NuvioClient._optional_string(source.get("title"))
        if not label:
            label = NuvioClient._optional_string(source.get("name"))
        if not label:
            label = NuvioClient._optional_string(source.get("catalogName"))
        catalog = source.get("catalog")
        if not label and isinstance(catalog, dict):
            label = NuvioClient._optional_string(catalog.get("name"))
        display = source.get("display")
        if not label and isinstance(display, dict):
            label = NuvioClient._optional_string(display.get("name"))

        provider = NuvioClient._optional_string(source.get("provider"))
        raw_filters = source.get("filters")
        filters = raw_filters if isinstance(raw_filters, dict) else {}

        if source_type and catalog_id:
            kind = "addon"
        elif provider.lower() == "tmdb" or isinstance(raw_filters, dict):
            kind = "tmdb"
        else:
            kind = "unknown"

        return {
            "id": NuvioClient._optional_string(source.get("id")),
            "kind": kind,
            "label": label,
            "provider": provider,
            "type": source_type,
            "catalog_id": catalog_id,
            "addon_id": NuvioClient._optional_string(source.get("addonId")),
            "media_type": NuvioClient._optional_string(source.get("mediaType")).lower(),
            "sort_by": NuvioClient._optional_string(source.get("sortBy")),
            "tmdb_source_type": NuvioClient._optional_string(source.get("tmdbSourceType")),
            "filters": filters,
        }

    def logout(self):
        if self.access_token:
            try:
                requests.post(
                    f"{self.BASE_URL}/auth/v1/logout",
                    headers=self._auth_headers,
                    timeout=self._effective_request_timeout(),
                )
            except requests.RequestException as error:
                kodilog(f"[NUVIO] logout request failed ({type(error).__name__})")
        self._clear_session()
        notification("Nuvio authorization removed.", time=3000)


def _setting_enabled(setting_id):
    value = get_setting(setting_id)
    return value is True or str(value).lower() == "true"


def is_nuvio_progress_sync_enabled():
    return bool(
        _setting_enabled("nuvio_enabled")
        and _setting_enabled("nuvio_authenticated")
        and get_setting("nuvio_access_token")
        and NuvioClient._profile_index(get_setting("nuvio_profile_id"))
    )
