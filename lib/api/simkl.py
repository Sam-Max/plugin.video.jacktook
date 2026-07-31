import contextlib
import time

import requests
import xbmc

from lib.clients.simkl import SIMKL_CLIENT_ID
from lib.gui.qr_progress_dialog import QRProgressDialog
from lib.jacktook.utils import ADDON_NAME, ADDON_PATH, ADDON_VERSION
from lib.utils.debrid.qrcode_utils import make_qrcode
from lib.utils.kodi.utils import (
    copy2clip,
    get_setting,
    kodilog,
    notification,
    set_setting,
    sleep,
)


class SimklClient:
    BASE_URL = "https://api.simkl.com"
    REQUEST_TIMEOUT = 5
    RATE_LIMIT_COOLDOWN = 20
    _scrobble_backoff_until = 0.0

    def __init__(self, client_id=None, access_token=None):
        client_id_override = client_id if client_id is not None else get_setting("simkl_client_id")
        self.client_id = str(client_id_override or "").strip() or SIMKL_CLIENT_ID
        self.access_token = str(access_token or get_setting("simkl_access_token") or "").strip()

    @property
    def _params(self):
        return {
            "client_id": self.client_id,
            "app-name": ADDON_NAME or "Jacktook",
            "app-version": ADDON_VERSION or "0.0.0",
        }

    @property
    def _headers(self):
        headers = {"User-Agent": f"{ADDON_NAME or 'Jacktook'}/{ADDON_VERSION or '0.0.0'}"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    @staticmethod
    def _positive_integer(value):
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value if value > 0 else None
        if isinstance(value, str) and value.strip().isdigit():
            parsed = int(value.strip())
            return parsed if parsed > 0 else None
        return None

    @staticmethod
    def _non_negative_integer(value):
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value if value >= 0 else None
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
        return None

    @classmethod
    def scrobble_payload(cls, data):
        if not isinstance(data, dict):
            return None
        ids = data.get("ids")
        tmdb_id = cls._positive_integer(ids.get("tmdb_id")) if isinstance(ids, dict) else None
        if not tmdb_id:
            return None
        try:
            progress = round(min(max(float(data.get("progress") or 0), 0), 100), 2)
        except (TypeError, ValueError):
            progress = 0.0

        payload = {"progress": progress}
        if data.get("mode") == "movies":
            payload["movie"] = {"ids": {"tmdb": tmdb_id}}
            return payload
        if data.get("mode") != "tv":
            return None

        tv_data = data.get("tv_data")
        if not isinstance(tv_data, dict):
            return None
        season = cls._non_negative_integer(tv_data.get("season"))
        episode = cls._positive_integer(tv_data.get("episode"))
        if season is None or not episode:
            return None
        payload["show"] = {"ids": {"tmdb": tmdb_id}}
        payload["episode"] = {"season": season, "number": episode}
        return payload

    def scrobble(self, action, data):
        if action not in ("start", "pause", "stop") or not self.client_id or not self.access_token:
            return False
        if time.monotonic() < type(self)._scrobble_backoff_until:
            return False
        payload = self.scrobble_payload(data)
        if payload is None:
            return False
        try:
            response = requests.post(
                f"{self.BASE_URL}/scrobble/{action}",
                params=self._params,
                headers=self._headers,
                json=payload,
                timeout=self.REQUEST_TIMEOUT,
            )
        except requests.RequestException as error:
            kodilog(f"[SIMKL] {action} transport failure ({type(error).__name__})")
            return False

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", self.RATE_LIMIT_COOLDOWN)
            try:
                cooldown = max(float(retry_after), self.RATE_LIMIT_COOLDOWN)
            except (TypeError, ValueError):
                cooldown = self.RATE_LIMIT_COOLDOWN
            type(self)._scrobble_backoff_until = time.monotonic() + cooldown
            kodilog(f"[SIMKL] {action} rate limited; suppressing scrobbles temporarily")
            return False
        if response.status_code == 400 and "RATE_LIMIT" in response.text.upper():
            type(self)._scrobble_backoff_until = time.monotonic() + self.RATE_LIMIT_COOLDOWN
            kodilog(f"[SIMKL] {action} lock active; suppressing scrobbles temporarily")
            return False
        if response.status_code >= 400:
            kodilog(f"[SIMKL] {action} rejected (HTTP {response.status_code}); continuing playback")
            return False
        return True

    def request_pin(self):
        if not self.client_id:
            notification("Simkl client ID is required before authorization.", time=5000)
            return None
        try:
            response = requests.get(
                f"{self.BASE_URL}/oauth/pin",
                params=self._params,
                headers=self._headers,
                timeout=self.REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            result = response.json()
        except (requests.RequestException, ValueError) as error:
            kodilog(f"[SIMKL] PIN request failed ({type(error).__name__})")
            notification("Unable to start Simkl authorization.", time=5000)
            return None
        if not isinstance(result, dict):
            notification("Simkl returned an invalid PIN response.", time=5000)
            return None
        required = ("user_code", "expires_in", "interval")
        verification_url = result.get("verification_uri") or result.get("verification_url")
        if not verification_url or any(not result.get(key) for key in required):
            notification("Simkl returned an invalid PIN response.", time=5000)
            return None
        result["verification_url"] = verification_url
        return result

    def authenticate(self):
        pin = self.request_pin()
        if not pin:
            return False
        try:
            expires_in = max(float(pin["expires_in"]), 1)
            interval = max(float(pin["interval"]), 1)
        except (TypeError, ValueError):
            notification("Simkl returned invalid PIN timing data.", time=5000)
            return False

        user_code = str(pin["user_code"])
        verification_url = str(pin["verification_url"])
        with contextlib.suppress(BaseException):
            copy2clip(user_code)
        dialog = QRProgressDialog("qr_dialog.xml", ADDON_PATH)
        monitor = xbmc.Monitor()
        deadline = time.monotonic() + expires_in
        try:
            dialog.setup(
                "Simkl Authorization",
                make_qrcode(verification_url),
                verification_url,
                user_code,
                is_debrid=False,
            )
            dialog.show_dialog()
            while True:
                if dialog.iscanceled or monitor.abortRequested():
                    return False
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                sleep(int(min(interval, remaining) * 1000))
                if time.monotonic() >= deadline:
                    break
                try:
                    response = requests.get(
                        f"{self.BASE_URL}/oauth/pin/{user_code}",
                        params=self._params,
                        headers=self._headers,
                        timeout=self.REQUEST_TIMEOUT,
                    )
                except requests.RequestException as error:
                    kodilog(f"[SIMKL] PIN polling failed ({type(error).__name__})")
                    return False
                if response.status_code == 429:
                    interval = min(max(interval * 2, interval + 1), 60)
                    continue
                if response.status_code >= 400:
                    return False
                try:
                    result = response.json()
                except ValueError:
                    return False
                if (
                    isinstance(result, dict)
                    and result.get("result") == "OK"
                    and result.get("access_token")
                ):
                    self.access_token = str(result["access_token"])
                    set_setting("simkl_access_token", self.access_token)
                    set_setting("simkl_authenticated", "true")
                    notification("Simkl authorization completed.", time=3000)
                    return True
                elapsed = expires_in - max(deadline - time.monotonic(), 0)
                dialog.update_progress(min(int(100 * elapsed / expires_in), 99))
        finally:
            with contextlib.suppress(BaseException):
                dialog.close_dialog()
        notification("Simkl authorization expired. Try again.", time=5000)
        return False

    def logout(self):
        self.access_token = ""
        set_setting("simkl_access_token", "")
        set_setting("simkl_authenticated", "false")
        notification("Simkl authorization removed.", time=3000)


def is_simkl_scrobbling_enabled():
    return bool(
        get_setting("simkl_enabled")
        and get_setting("simkl_scrobbling_enabled")
        and get_setting("simkl_authenticated")
        and get_setting("simkl_access_token")
    )
