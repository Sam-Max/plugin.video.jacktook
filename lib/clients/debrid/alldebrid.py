
from lib.clients.debrid.base import DebridClient, ProviderException


class AllDebrid(DebridClient):
    BASE_URL = "https://api.alldebrid.com/v4"

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
        data,
        json,
        params,
        is_return_none: bool = False,
        is_expected_to_fail: bool = False,
    ):
        params = params or {}
        url = self.BASE_URL + url
        return super()._make_request(
            method, url, data, json, params, is_return_none, is_expected_to_fail
        )

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
            else:
                raise ProviderException(
                    f"Failed to add magnet link to AllDebrid {response_data}"
                )

    def add_magnet_link(self, magnet_link):
        response_data = self._make_request(
            "POST", "/magnet/upload", data={"magnets[]": magnet_link}
        )
        self._validate_error_response(response_data)
        return response_data

    def get_user_torrent_list(self):
        return self._make_request("GET", "/magnet/status")

    def get_torrent_info(self, magnet_id):
        response = self._make_request("GET", "/magnet/status", params={"id": magnet_id})
        return response.get("data", {}).get("magnets")

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

    def create_download_link(self, link):
        response = self._make_request(
            "GET",
            "/link/unlock",
            params={"link": link},
            is_expected_to_fail=True,
        )
        if response.get("status") == "success":
            return response
        raise ProviderException(
            f"Failed to create download link from AllDebrid {response}",
            "transfer_error.mp4",
        )

    def delete_torrent(self, magnet_id):
        return self._make_request("GET", "/magnet/delete", params={"id": magnet_id})

    def get_user_info(self):
        return self._make_request("GET", "/user")
