from lib.api.debrid.base import DebridClient, ProviderException


class Offcloud(DebridClient):
    BASE_URL = "https://offcloud.com/api"
    OAUTH_BASE_URL = "https://offcloud.com"
    DEVICE_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:device_code"

    def initialize_headers(self):
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"

    def disable_access_token(self):
        pass

    def _handle_service_specific_errors(self, error_data: dict, status_code: int):
        error_code = error_data.get("error")
        if error_code == "NOAUTH":
            raise ProviderException("Invalid Offcloud token", status_code, error_data)
        if error_code == "Bad archive":
            raise ProviderException(
                "Offcloud cannot explore single-file torrents", status_code, error_data
            )

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
        return super()._make_request(
            method,
            self.BASE_URL + url,
            data=data,
            params=params or {},
            json=json,
            is_return_none=is_return_none,
            is_expected_to_fail=is_expected_to_fail,
        )

    def _make_oauth_request(self, method, url, json=None, is_expected_to_fail=False):
        headers = self.headers
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        try:
            return super()._make_request(
                method,
                self.OAUTH_BASE_URL + url,
                json=json,
                params={},
                is_expected_to_fail=is_expected_to_fail,
            )
        finally:
            self.headers = headers

    def get_device_code(self):
        return self._make_oauth_request("POST", "/oauth/device/code", json={})

    def get_token(self, device_code, is_expected_to_fail=False):
        return self._make_oauth_request(
            "POST",
            "/oauth/token",
            json={"grant_type": self.DEVICE_GRANT_TYPE, "device_code": device_code},
            is_expected_to_fail=is_expected_to_fail,
        )

    def authorize(self, device_code):
        return self.get_token(device_code, is_expected_to_fail=True)

    def remove_auth(self):
        from lib.utils.kodi.utils import dialog_ok, set_setting, translation

        self.token = ""
        set_setting("offcloud_token", "")
        set_setting("offcloud_user", "")
        set_setting("offcloud_authorized", "false")
        dialog_ok(translation(90544), translation(90561))

    def get_account_info(self):
        return self._make_request("GET", "/account/info")

    def get_cache_info(self, urls, include_files=False):
        return self._make_request(
            "POST",
            "/cache/info",
            json={"urls": urls, "includeFiles": include_files},
        )

    def create_cache_download(self, url):
        return self._make_request("POST", "/cache/download", json={"url": url})

    def add_cloud_download(self, url):
        return self._make_request("POST", "/cloud", json={"url": url})

    def get_cloud_status(self, request_id):
        response = self._make_request("POST", "/cloud/status", json={"requestId": request_id})
        status = response.get("status")
        return status if isinstance(status, dict) else response

    def explore_cloud_download(self, request_id, detailed=True):
        params = {"format": "detailed"} if detailed else None
        return self._make_request(
            "GET",
            f"/cloud/explore/{request_id}",
            params=params,
            is_expected_to_fail=True,
        )

    def get_cloud_history(self):
        return self._make_request("GET", "/cloud/history")

    def remove_cloud_downloads(self, request_ids):
        return self._make_request("POST", "/cloud/remove", json={"requests": request_ids})
