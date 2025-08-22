from time import time
from lib.api.debrid.base import DebridClient
from lib.gui.qr_progress_dialog import QRProgressDialog
from lib.jacktook.utils import kodilog
from lib.utils.debrid.qrcode_utils import make_qrcode
from lib.utils.general.utils import DebridType
from lib.utils.kodi.utils import ADDON_PATH, copy2clip, dialog_ok, set_setting, sleep


class Debrider(DebridClient):
    BASE_URL = "https://debrider.app/api/v1"
    AUTH_URL = "https://debrider.app/api/app"

    def __init__(self, token, user_ip=None):
        self.user_ip = user_ip
        super().__init__(token)

    def auth(self):
        response = self.get_device_code()
        kodilog("Debrider: Requesting device code for authentication.")
        kodilog("Debrider: Response received: %s" % response)

        if response:
            interval = int(response["interval"])
            expires_in = int(response["expires_in"])
            device_code = response["device_code"]
            user_code = response["user_code"]
            auth_url = response["verification_url"]
            qr_code = make_qrcode(auth_url)
            copy2clip(auth_url)
            progressDialog = QRProgressDialog("qr_dialog.xml", ADDON_PATH)
            progressDialog.setup(
                "Debrider Auth",
                qr_code,
                auth_url,
                user_code,
                DebridType.DB
            )
            progressDialog.show_dialog()
            start_time = time()
            while time() - start_time < expires_in:
                if progressDialog.iscanceled:
                    progressDialog.close_dialog()
                    return
                elapsed = time() - start_time
                percent = int((elapsed / expires_in) * 100)
                progressDialog.update_progress(percent)
                try:
                    response = self.get_device_auth_status(device_code)
                    if "apikey" in response:
                        self.token = response["apikey"]
                        progressDialog.close_dialog()
                        set_setting("debrider_token", self.token)
                        set_setting("debrider_authorized", "true")
                        self.initialize_headers()
                        dialog_ok("Success", "Authentication completed.")
                        return
                    sleep(1000 * interval)
                except Exception as e:
                    progressDialog.close_dialog()
                    dialog_ok("Error:", f"Error: {e}.")
                    return

    def remove_auth(self):
        set_setting("debrider_token", "")
        set_setting("debrider_authorized", "false")
        dialog_ok("Success", "Authentification Removed.")

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
