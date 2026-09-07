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


class NuvioClient:
    BASE_URL = "https://api.nuvio.tv"
    PUBLISHABLE_KEY = "sb_publishable_1Clq8rlTVACkdcZuqr6_AD__xUUC_EN"
    REQUEST_TIMEOUT = 5
    REFRESH_LEEWAY_SECONDS = 60

    def __init__(self, access_token=None, refresh_token=None, expires_at=None, profile_id=None):
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
        self._last_token_failure_status = None

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
                timeout=self.REQUEST_TIMEOUT,
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
                request_args = {"headers": self._auth_headers, "timeout": self.REQUEST_TIMEOUT}
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
                    timeout=self.REQUEST_TIMEOUT,
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
                timeout=self.REQUEST_TIMEOUT,
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

    def logout(self):
        if self.access_token:
            try:
                requests.post(
                    f"{self.BASE_URL}/auth/v1/logout",
                    headers=self._auth_headers,
                    timeout=self.REQUEST_TIMEOUT,
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
