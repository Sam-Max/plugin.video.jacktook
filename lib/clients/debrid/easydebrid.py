from lib.clients.debrid.base import DebridClient, ProviderException


class EasyDebrid(DebridClient):
    BASE_URL = "https://easydebrid.com/api/v1"

    def __init__(self, token, user_ip):
        self.user_ip = user_ip
        super().__init__(token)

    def initialize_headers(self):
        self.headers = {"Authorization": f"Bearer {self.token}"}
        if self.user_ip:
            self.headers["X-Forwarded-For"] = self.user_ip

    def disable_access_token(self):
        pass

    def _handle_service_specific_errors(self, error_data: dict, status_code: int):
        error_code = error_data.get("error")
        if error_code == "Unsupported link for direct download.":
            raise ProviderException(
                "Unsupported link for direct download.",
            )

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
        url = self.BASE_URL + url
        return super()._make_request(
            method,
            url,
            data,
            params=params,
            json=json,
            is_return_none=is_return_none,
            is_expected_to_fail=is_expected_to_fail,
        )

    def get_torrent_instant_availability(self, urls):
        return self._make_request(
            "POST",
            "/link/lookup",
            json={"urls": urls},
        )

    def create_download_link(self, magnet):
        return self._make_request(
            "POST",
            "/link/generate",
            json={"url": magnet},
        )

    def get_torrent_info(self, torrent_id: str):
        pass

    def get_user_info(self):
        return self._make_request("GET", "/user/details")
