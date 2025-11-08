import requests
from lib.api.debrid.base import DebridClient, ProviderException
from lib.gui.qr_progress_dialog import QRProgressDialog
from lib.jacktook.utils import ADDON_PATH, kodilog
from lib.utils.debrid.qrcode_utils import make_qrcode
from lib.utils.general.utils import DebridType
from lib.utils.kodi.utils import copy2clip, dialog_ok, set_setting, sleep
from time import time


class AllDebrid(DebridClient):
    BASE_URL = "https://api.alldebrid.com/v4.1"
    USER_AGENT = "jacktook"

    def __init__(self, token: str):
        super().__init__(token)

    def initialize_headers(self):
        self.headers = {"Authorization": f"Bearer {self.token}"}

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
        version_number: str = "v4.1",
    ):
        params = params or {}
        if version_number == "v4":
            self.BASE_URL = "https://api.alldebrid.com/v4.0"
        url = f"{self.BASE_URL}{url}"
        return super()._make_request(
            method, url, data, json, params, is_return_none, is_expected_to_fail
        )

    def auth(self):
        """
        Start PIN-based auth flow for AllDebrid.
        """
        response = self.get_ping()
        result = response["data"]

        expires_in = result["expires_in"]
        sleep_interval = 5
        user_code = result["pin"]
        check_id = result["check"]
        user_url = result["user_url"]

        qr_code = make_qrcode(user_url)
        copy2clip(user_url)

        progressDialog = QRProgressDialog("qr_dialog.xml", ADDON_PATH)
        progressDialog.setup(
            f"{DebridType.AD} Auth",
            qr_code,
            user_url,
            user_code,
            DebridType.AD,
        )
        progressDialog.show_dialog()

        start_time = time()
        while time() - start_time < expires_in and not self.token:
            sleep(1000 * sleep_interval)
            if progressDialog.iscanceled:
                progressDialog.close_dialog()
                return
            response = self.poll_auth(check_id, user_code)
            activated = response["activated"]
            if not activated:
                elapsed = time() - start_time
                percent = int((elapsed / expires_in) * 100)
                progressDialog.update_progress(percent)
                continue
            try:
                if "apikey" in response:
                    self.token = response.get("apikey", "")
                    set_setting("alldebrid_token", self.token)
                    set_setting("alldebrid_authorized", "true")

                    self.initialize_headers()

                    response = self.get_user_info()
                    username = response["user"]["username"]
                    set_setting("alldebrid_user", str(username))

                    progressDialog.update_progress(100, "Authentication completed.")
                    progressDialog.close_dialog()
                    return
                else:
                    elapsed = time() - start_time
                    percent = int((elapsed / expires_in) * 100)
                    progressDialog.update_progress(percent)
            except Exception as e:
                progressDialog.close_dialog()
                dialog_ok("Auth Error", f"Error: {e}")
                return

    def poll_auth(self, check_id: str, pin: str):
        response = self._make_request(
            "POST",
            "/pin/check",
            data={"check": check_id, "pin": pin},
            is_expected_to_fail=True,
        )
        kodilog(f"AllDebrid poll_auth response: {response}")
        return response.get("data", {})

    def get_ping(self):
        return self._make_request("GET", "/pin/get")

    def remove_auth(self):
        self.token = ""
        set_setting("alldebrid_token", "")
        set_setting("alldebrid_authorized", "false")
        set_setting("alldebrid_user", "")
        dialog_ok("Success", "Authentification Removed.")

    @staticmethod
    def _validate_error_response(response_data):
        if response_data.get("status") != "success":
            error_code = response_data.get("error", {}).get("code")
            if error_code == "AUTH_BAD_APIKEY":
                raise ProviderException("Invalid AllDebrid API key")
            elif error_code == "NO_SERVER":
                raise ProviderException(
                    f"Failed to add magnet link to AllDebrid {response_data}"
                )
            elif error_code == "AUTH_BLOCKED":
                raise ProviderException("API got blocked on AllDebrid")
            elif error_code == "MAGNET_MUST_BE_PREMIUM":
                raise ProviderException("Torrent must be premium on AllDebrid")
            elif error_code in {"MAGNET_TOO_MANY_ACTIVE", "MAGNET_TOO_MANY"}:
                raise ProviderException("Too many active torrents on AllDebrid")
            elif error_code == "MAGNET_INVALID_ID":
                raise ProviderException("Invalid magnet link for AllDebrid")
            else:
                raise ProviderException(
                    f"Failed to add magnet link to AllDebrid {response_data}"
                )

    def add_magnet(self, magnet_link):
        response = self._make_request(
            "POST", "/magnet/upload", data={"magnets[]": magnet_link}
        )
        self._validate_error_response(response)
        return response

    def get_user_torrent_list(self):
        return self._make_request("GET", "/magnet/status")

    def get_torrent_info(self, id):
        return self._make_request("POST", "/magnet/status", data={"id": id})

    def get_files_and_links(self, id):
        response = self._make_request(
            "POST",
            "/magnet/files",
            data={"id[]": id},
            version_number="v4",
        )
        self._validate_error_response(response)
        return response.get("data", {}).get("magnets", {})

    def get_torrent_instant_availability(self, magnet_links):
        response = self._make_request(
            "POST", "/magnet/instant", data={"magnets[]": magnet_links}
        )
        return response.get("data", {}).get("magnets", [])

    def get_available_torrent(self, info_hash):
        available_torrents = self.get_user_torrent_list()
        self._validate_error_response(available_torrents)
        if not available_torrents.get("data"):
            return None
        for torrent in available_torrents["data"]["magnets"]:
            if torrent["hash"] == info_hash:
                return torrent
        return None

    def create_download_link(self, link: str):
        return self._make_request(
            "POST",
            "/link/unlock",
            data={"link": link},
            is_expected_to_fail=True,
        )

    def get_redirected_link(self, link: str) -> str:
        response = self._make_request(
            "GET",
            "/link/redirector",
            params={"link": link},
            is_expected_to_fail=True,
        )
        kodilog(f"AllDebrid get_redirected_link response: {response}")
        return response.get("data", {}).get("link")

    def delete_torrent(self, magnet_id):
        return self._make_request("GET", "/magnet/delete", params={"id": magnet_id})

    def get_user_info(self):
        response = self._make_request("GET", "/user")
        return response.get("data", {})
