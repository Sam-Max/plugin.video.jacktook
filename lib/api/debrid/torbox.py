from lib.api.debrid.base import DebridClient, ProviderException
from lib.utils.kodi.utils import (
    dialog_ok,
    kodilog,
    notification,
    set_setting,
    copy2clip,
    sleep as ksleep,
)
from lib.utils.debrid.qrcode_utils import make_qrcode
from lib.gui.qr_progress_dialog import QRProgressDialog
from lib.jacktook.utils import ADDON_PATH
from lib.utils.general.utils import DebridType
from time import time
import datetime
import time as time_lib
import requests


class Torbox(DebridClient):
    def __init__(self, token, timeout=15):
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(max_retries=1)
        session.mount("https://", adapter)
        super().__init__(token, timeout, session)

    BASE_URL = "https://api.torbox.app/v1/api"

    def initialize_headers(self):
        self.headers = {
            "User-Agent": "Jacktook/1.0",
            "Accept": "application/json",
        }
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"

    def disable_access_token(self):
        pass

    def _handle_service_specific_errors(self, error_data: dict, status_code: int):
        error_code = error_data.get("error")
        if error_code in {"BAD_TOKEN", "AUTH_ERROR", "OAUTH_VERIFICATION_ERROR"}:
            raise ProviderException("Invalid Torbox token")
        elif error_code == "DOWNLOAD_TOO_LARGE":
            raise ProviderException("Download size too large for the user plan")
        elif error_code in {"ACTIVE_LIMIT", "MONTHLY_LIMIT"}:
            raise ProviderException("Download limit exceeded")
        elif error_code in {"DOWNLOAD_SERVER_ERROR", "DATABASE_ERROR"}:
            raise ProviderException("Torbox server error")

    def _make_request(
        self,
        method,
        url,
        data=None,
        params=None,
        json=None,
        is_return_none=False,
        is_expected_to_fail=False,
    ):
        params = params or {}
        url = self.BASE_URL + url
        return super()._make_request(
            method,
            url,
            data=data,
            params=params,
            json=json,
            is_return_none=is_return_none,
            is_expected_to_fail=is_expected_to_fail,
        )

    def add_magnet_link(self, magnet_link):
        return self._make_request(
            "POST",
            "/torrents/createtorrent",
            data={"magnet": magnet_link, "seed": 3, "allow_zip": "false"},
            is_expected_to_fail=False,
        )

    def get_user_torrent_list(self):
        return self._make_request(
            "GET",
            "/torrents/mylist",
            params={"bypass_cache": "true"},
        )

    def get_torrent_info(self, magnet_id):
        response = self.get_user_torrent_list()
        torrent_list = response.get("data", {})
        for torrent in torrent_list:
            if torrent.get("magnet", "") == magnet_id:
                return torrent

    def get_available_torrent(self, info_hash):
        response = self.get_user_torrent_list()
        torrent_list = response.get("data", {})
        for torrent in torrent_list:
            if torrent.get("hash", "") == info_hash:
                return torrent

    def get_torrent_instant_availability(self, torrent_hashes):
        return self._make_request(
            "POST",
            "/torrents/checkcached",
            params={"format": "list"},
            json={"hashes": torrent_hashes},
        )

    def create_download_link(self, torrent_id, filename, user_ip=None):
        params = {
            "token": self.token,
            "torrent_id": torrent_id,
            "file_id": filename,
        }
        if user_ip:
            params["user_ip"] = user_ip

        response = self._make_request(
            "GET",
            "/torrents/requestdl",
            params=params,
            is_expected_to_fail=True,
        )
        if response.get("success"):
            return response
        else:
            detail = response.get("detail", "Unknown error")
            notification(f"Failed to create download link: {detail}")
            return None

    def delete_torrent(self, torrent_id):
        self._make_request(
            "POST",
            "/torrents/controltorrent",
            data={"torrent_id": torrent_id, "operation": "Delete"},
            is_expected_to_fail=False,
        )

    def download(self, magnet_link):
        pass

    def get_device_code(self):
        return self._make_request(
            "GET",
            "/user/auth/device/start",
            params={"app": "Jacktook"},
        )

    def get_token(self, device_code, is_expected_to_fail=False):
        return self._make_request(
            "POST",
            "/user/auth/device/token",
            json={"device_code": device_code},
            is_expected_to_fail=is_expected_to_fail,
        )

    def authorize(self, device_code):
        response_data = self.get_token(device_code, is_expected_to_fail=True)
        if response_data.get("success"):
            token_data = response_data.get("data", {})
            # The structure is data: { access_token: "...", ... }
            if isinstance(token_data, dict):
                 return {"token": token_data.get("access_token")}
            # Fallback if API changes or logical mismatch, though snippet suggests structure above
            return {"token": token_data} 
        return response_data

    def remove_auth(self):
        self.token = ""
        set_setting("torbox_token", "")
        set_setting("torbox_user", "")
        set_setting("torbox_enabled", "false")
        dialog_ok("Success", "Authentification Removed.")

    def auth(self):
        response = self.get_device_code()
        if response and response.get("success"):
            data = response.get("data", {})
            sleep_interval = int(data.get("interval", 5))
            expires_in = int(data.get("expires_in", 600))
            device_code = data.get("device_code")
            user_code = data.get("code")
            auth_url = data.get("verification_url")
            friendly_url = data.get("friendly_verification_url") or auth_url

            qr_code = make_qrcode(auth_url)
            copy2clip(auth_url)

            progressDialog = QRProgressDialog("qr_dialog.xml", ADDON_PATH)
            progressDialog.setup(
                "Torbox Auth",
                qr_code,
                friendly_url,
                user_code,
                DebridType.TB,
            )
            progressDialog.show_dialog()

            start_time = time()
            while time() - start_time < expires_in:
                ksleep(1000 * sleep_interval)
                if progressDialog.iscanceled:
                    progressDialog.close_dialog()
                    return
                try:
                    response = self.authorize(device_code)
                except:
                    continue
                try:
                    if "token" in response:
                        self.token = response["token"]
                        set_setting("torbox_token", self.token)
                        set_setting("torbox_enabled", "true")

                        self.initialize_headers()

                        user_data = self.get_user()
                        if user_data.get("success"):
                            set_setting("torbox_user", user_data.get("data", {}).get("customer_email", ""))
                        
                        progressDialog.update_progress(100, "Authentication completed.")
                        progressDialog.close_dialog()
                        dialog_ok("Success", "Torbox authentication successful.")
                        return
                    else:
                        elapsed = time() - start_time
                        percent = int((elapsed / expires_in) * 100)
                        progressDialog.update_progress(percent)
                except Exception as e:
                    progressDialog.close_dialog()
                    dialog_ok("Auth Error:", f"Error: {e}")
                    return

    def get_user(self):
        return self._make_request("GET", "/user/me")

    def days_remaining(self):
        try:
            account_info = self.get_user()
            if not account_info.get("success"):
                return None
            
            data = account_info.get("data", {})
            expires_at = data.get("premium_expires_at")
            if not expires_at:
                return None

            FormatDateTime = '%Y-%m-%dT%H:%M:%SZ'
            try:
                expires = datetime.datetime.strptime(expires_at, FormatDateTime)
            except ValueError:
                # Handle cases where microsecond might be missing or different format
                expires = datetime.datetime(*(time_lib.strptime(expires_at, FormatDateTime)[0:6]))
            
            days = (expires - datetime.datetime.today()).days
            return days
        except Exception as e:
            kodilog(f"Error calculating days remaining: {e}")
            return None