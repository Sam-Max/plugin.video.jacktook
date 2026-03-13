from lib.api.debrid.base import DebridClient, ProviderException
from lib.services.debrid.auth import run_premiumize_auth


class Premiumize(DebridClient):
    BASE_URL = "https://www.premiumize.me/api"
    OAUTH_TOKEN_URL = "https://www.premiumize.me/token"
    OAUTH_URL = "https://www.premiumize.me/authorize"
    CLIENT_ID = "855400527"

    def initialize_headers(self):
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "User-Agent": "Jacktook/1.0",
            "Accept": "application/json",
        }

    def disable_access_token(self):
        pass

    def _handle_service_specific_errors(self, error_data, status_code: int):
        pass

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
        return super()._make_request(
            method,
            url,
            data=data,
            params=params,
            json=json,
            is_return_none=is_return_none,
            is_expected_to_fail=is_expected_to_fail,
        )

    def get_device_code(self):
        return self._make_request(
            "POST",
            self.OAUTH_TOKEN_URL,
            data={"response_type": "device_code", "client_id": self.CLIENT_ID},
        )

    def authorize(self, device_code):
        return self._make_request(
            "POST",
            self.OAUTH_TOKEN_URL,
            is_expected_to_fail=True,
            data={
                "grant_type": "device_code",
                "client_id": self.CLIENT_ID,
                "code": device_code,
            },
        )

    def auth(self):
        run_premiumize_auth(self)

    def download(self):
        pass

    def create_or_get_folder_id(self, info_hash, folder_id: str):
        folder_data = self.get_folder_list(folder_id)
        for folder in folder_data["content"]:
            if folder["name"] == info_hash:
                return folder["id"]

        folder_data = self.create_folder(info_hash)
        if folder_data.get("status") != "success":
            return
        return folder_data.get("id")

    def add_magnet_link(self, magnet_link: str, folder_id: str):
        return self._make_request(
            "POST",
            f"{self.BASE_URL}/transfer/create",
            data={"src": magnet_link, "folder_id": folder_id},
        )

    def create_download_link(self, magnet_link: str):
        return self._make_request(
            "POST",
            f"{self.BASE_URL}/transfer/directdl",
            data={"src": magnet_link},
        )

    def create_folder(self, name, parent_id=None):
        return self._make_request(
            "POST",
            f"{self.BASE_URL}/folder/create",
            data={"name": name, "parent_id": parent_id},
        )

    def get_transfer_list(self):
        return self._make_request("GET", f"{self.BASE_URL}/transfer/list")

    def get_torrent_info(self, torrent_id):
        transfer_list = self.get_transfer_list()
        torrent_info = next(
            (
                torrent
                for torrent in transfer_list["transfers"]
                if torrent["id"] == torrent_id
            ),
            None,
        )
        return torrent_info

    def get_folder_list(self, folder_id: str):
        return self._make_request(
            "GET",
            f"{self.BASE_URL}/folder/list",
            params={"id": folder_id} if folder_id else None,
        )

    def delete_torrent(self, torrent_id):
        return self._make_request(
            "POST", f"{self.BASE_URL}/transfer/delete", data={"id": torrent_id}
        )

    def get_torrent_instant_availability(self, torrent_hashes):
        results = self._make_request(
            "GET", f"{self.BASE_URL}/cache/check", params={"items[]": torrent_hashes}
        )
        if results.get("status") != "success":
            raise ProviderException(
                "Failed to get instant availability from Premiumize",
            )
        return results

    def get_available_torrent(self, info_hash: str, torrent_name):
        torrent_list_response = self.get_transfer_list()
        if torrent_list_response.get("status") != "success":
            if torrent_list_response.get("message") == "Not logged in.":
                raise ProviderException("Premiumize is not logged in.")
            raise ProviderException("Failed to get torrent info from Premiumize")

        available_torrents = torrent_list_response["transfers"]
        for torrent in available_torrents:
            src = torrent.get("src")
            if (
                (src and info_hash in src)
                or info_hash == torrent["name"]
                or torrent_name == torrent["name"]
            ):
                return torrent

    def get_account_info(self):
        return self._make_request("GET", f"{self.BASE_URL}/account/info")

    def days_remaining(self):
        try:
            account = self.get_account_info()
            if not account or account.get("status") != "success":
                return None

            premium_until = account.get("premium_until")
            if not premium_until:
                return None

            import datetime

            expires = datetime.datetime.fromtimestamp(premium_until)
            days = (expires - datetime.datetime.now()).days
            return days
        except Exception as e:
            # kodilog(f"Error calculating Premiumize days remaining: {e}")
            return None
