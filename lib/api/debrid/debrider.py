from lib.api.debrid.base import DebridClient
from lib.jacktook.utils import kodilog
from lib.utils.kodi.utils import dialog_ok, set_setting, translation
from lib.services.debrid.auth import run_debrider_auth


class Debrider(DebridClient):
    BASE_URL = "https://debrider.app/api/v1"
    AUTH_URL = "https://debrider.app/api/app"

    def __init__(self, token, user_ip=None):
        self.user_ip = user_ip
        super().__init__(token)

    def auth(self):
        kodilog("Debrider: Requesting device code for authentication.")
        run_debrider_auth(self)

    def remove_auth(self):
        set_setting("debrider_token", "")
        set_setting("debrider_authorized", "false")
        dialog_ok(translation(90544), translation(90561))

    def initialize_headers(self):
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "User-Agent": "Jacktook/1.0",
            "Accept": "application/json",
        }
        if self.user_ip:
            self.headers["X-Forwarded-For"] = self.user_ip

    def disable_access_token(self):
        pass

    def _handle_service_specific_errors(self, error_data: dict, status_code: int):
        pass

    def _make_request(
        self,
        method: str,
        url: str,
        data=None,
        params=None,
        json=None,
        is_return_none: bool = False,
        is_expected_to_fail: bool = False,
    ):
        params = params or {}
        return super()._make_request(
            method,
            url,
            data,
            params=params,
            json=json,
            is_return_none=is_return_none,
            is_expected_to_fail=is_expected_to_fail,
        )

    def get_device_auth_status(self, code):
        "Check the status of device authentication using a code."
        return self._make_request(
            "GET",
            f"{self.AUTH_URL}/device/auth",
            params={"code": code},
            is_expected_to_fail=True,
        )

    def get_device_code(self):
        return self._make_request(
            "GET",
            f"{self.AUTH_URL}/device/code",
        )

    def get_torrent_instant_availability(self, urls):
        return self._make_request(
            "POST",
            f"{self.BASE_URL}/link/lookup",
            json={"data": urls},
        )

    def create_download_link(self, magnet):
        return self._make_request(
            "POST",
            f"{self.BASE_URL}/link/generate",
            json={"data": magnet},
        )

    def add_torrent_file(self, magnet):
        return self._make_request(
            "POST",
            f"{self.BASE_URL}/tasks",
            json={"type": "magnet", "data": magnet},
        )

    def get_user_info(self):
        return self._make_request("GET", f"{self.BASE_URL}/account")

    def days_remaining(self):
        try:
            user = self.get_user_info()
            if not user or "subscription" not in user:
                return None

            premium_until = user["subscription"].get("premium_until")
            if not premium_until:
                return None

            import datetime

            try:
                expires = datetime.datetime.strptime(
                    premium_until, "%Y-%m-%dT%H:%M:%S.%fZ"
                )
            except ValueError:
                expires = datetime.datetime.strptime(
                    premium_until, "%Y-%m-%dT%H:%M:%SZ"
                )

            days = (expires - datetime.datetime.utcnow()).days
            return days
        except Exception as e:
            # kodilog(f"Error calculating Debrider days remaining: {e}")
            return None
