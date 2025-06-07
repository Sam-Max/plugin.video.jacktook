from lib.clients.debrid.base import DebridClient, ProviderException
from lib.utils.kodi.utils import notification


class Torbox(DebridClient):
    BASE_URL = "https://api.torbox.app/v1/api"

    def initialize_headers(self):
        if self.token:
            self.headers = {"Authorization": f"Bearer {self.token}"}

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
            data={"magnet": magnet_link},
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
            "GET",
            "/torrents/checkcached",
            params={"hash": torrent_hashes, "format": "object"},
        )

    def create_download_link(self, torrent_id, filename, user_ip):
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
        if "successfully" in response.get("detail"):
            return response
        raise ProviderException(
            f"Failed to create download link from Torbox {response}",
        )

    def download(self, magnet):
        response_data = self.add_magnet_link(magnet)
        if response_data.get("detail") is False:
            notification(f"Failed to add magnet link to Torbox {response_data}")
        else:
            notification(f"Magnet sent to cloud")

    def delete_torrent(self, torrent_id):
        self._make_request(
            "POST",
            "/torrents/controltorrent",
            data={"torrent_id": torrent_id, "operation": "Delete"},
            is_expected_to_fail=False,
        )
