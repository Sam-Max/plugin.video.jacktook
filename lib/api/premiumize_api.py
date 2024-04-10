import time
import traceback
import requests
from requests import RequestException, JSONDecodeError
from typing import Union, List, Optional, Dict
from lib.utils.kodi import copy2clip, log
from lib.utils.kodi import sleep as ksleep
from typing import Any
from lib.utils.kodi import (
    copy2clip,
    dialog_ok,
    set_setting,
    progressDialog,
)


class DebridClient:
    def __init__(self, token=None):
        self.token = token
        self.headers = {}
        self.initialize_headers()

    def _make_request(
        self,
        method: str,
        url: str,
        data=None,
        params=None,
        is_return_none=False,
        is_expected_to_fail=False,
    ) -> dict:
        response = self._perform_request(method, url, data, params)
        self._handle_errors(response, is_expected_to_fail)
        return self._parse_response(response, is_return_none)

    def _perform_request(self, method, url, data, params):
        try:
            return requests.request(
                method,
                url,
                params=params,
                data=data,
                headers=self.headers,
                timeout=15,
            )
        except requests.exceptions.Timeout:
            raise ProviderException("Request timed out.")
        except requests.exceptions.ConnectionError:
            raise ProviderException("Failed to connect to Debrid service.")

    def _handle_errors(self, response, is_expected_to_fail):
        try:
            response.raise_for_status()
        except RequestException as error:
            if is_expected_to_fail:
                return

            if error.response.status_code == 401:
                raise ProviderException("Invalid token")

            formatted_traceback = "".join(traceback.format_exception(error))
            raise ProviderException(
                f"API Error {error.response.text} \n{formatted_traceback}",
            )

    @staticmethod
    def _parse_response(response, is_return_none):
        if is_return_none:
            return {}
        try:
            return response.json()
        except JSONDecodeError as error:
            raise ProviderException(
                f"Failed to parse response error: {error}. \nresponse: {response.text}"
            )

    def initialize_headers(self):
        raise NotImplementedError

    def disable_access_token(self):
        raise NotImplementedError

    def wait_for_status(
        self,
        torrent_id: str,
        target_status: Union[str, int],
        max_retries: int,
        retry_interval: int,
    ):
        """Wait for the torrent to reach a particular status."""
        retries = 0
        while retries < max_retries:
            torrent_info = self.get_torrent_info(torrent_id)
            if torrent_info["status"] == target_status:
                return torrent_info
            time.sleep(retry_interval)
            retries += 1
        raise ProviderException(
            f"Torrent debrid_id not reach {target_status} status.",
        )

    def get_torrent_info(self, torrent_id):
        raise NotImplementedError


class Premiumize(DebridClient):
    BASE_URL = "https://www.premiumize.me/api"
    OAUTH_TOKEN_URL = "https://www.premiumize.me/token"
    OAUTH_URL = "https://www.premiumize.me/authorize"
    CLIENT_ID = "855400527"

    def __init__(self, token=None):
        self.token = token
        self.headers = {}
        self.initialize_headers()

    def initialize_headers(self):
        if self.token:
            self.headers = {"Authorization": f"Bearer {self.token}"}

    def get_token(self, code):
        return self._make_request(
            "POST",
            self.OAUTH_TOKEN_URL,
            data={
                "client_id": self.OAUTH_CLIENT_ID,
                "client_secret": self.OAUTH_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": self.REDIRECT_URI,
            },
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
        self.token = ""
        response = self.get_device_code()
        user_code = response["user_code"]
        try:
            copy2clip(user_code)
        except:
            pass
        content = "%s[CR]%s[CR]%s" % (
            "Authorize Debrid Services",
            "Navigate to: [B]%s[/B]" % response.get("verification_uri"),
            "Enter the following code: [COLOR orangered][B]%s[/B][/COLOR]" % user_code,
        )
        progressDialog.create("Premiumize Auth")
        progressDialog.update(-1, content)
        device_code = response["device_code"]
        expires_in = int(response["expires_in"])
        sleep_interval = int(response["interval"])
        start, time_passed = time.time(), 0
        while (
            not progressDialog.iscanceled()
            and time_passed < expires_in
            and not self.token
        ):
            ksleep(1000 * sleep_interval)
            response = self.authorize(device_code)
            if "error" in response:
                time_passed = time.time() - start
                progress = int(100 * time_passed / float(expires_in))
                progressDialog.update(progress, content)
                continue
            try:
                progressDialog.close()
                self.token = str(response["access_token"])
                set_setting("premiumize_token", self.token)
                dialog_ok("Success:", "Authentication completed.")
            except Exception as e:
                dialog_ok("Error:", f"Error: {e}.")
                break
        try:
            progressDialog.close()
        except:
            pass

    def download(self, magnet):
        info_hash = magnet_to_info_hash(magnet)
        folder_id = self.create_or_get_folder_id(info_hash)
        response_data = self.add_magent_link(magnet, folder_id)
        if "error" in response_data.get("status"):
            log(f"Failed to add magnet to Premiumize {response_data.get('message')}")
            return
        torrent_id = response_data["id"]
        torr_info = self.get_torrent_info(torrent_id)
        if torr_info["status"] == "finished":
            if torr_info["folder_id"] is None:
                torr_folder_data = self.get_folder_list(
                    self.create_or_get_folder_id(info_hash)
                )
            else:
                torr_folder_data = self.get_folder_list(torr_info["folder_id"])

    def create_or_get_folder_id(self, info_hash):
        folder_data = self.get_folder_list()
        for folder in folder_data["content"]:
            if folder["name"] == info_hash:
                return folder["id"]

        folder_data = self.create_folder(info_hash)
        if folder_data.get("status") != "success":
            log("Folder already created in meanwhile")
            return
        return folder_data.get("id")

    def add_magent_link(self, magnet_link: str, folder_id: str = None):
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

    def get_folder_list(self, folder_id: str = None):
        return self._make_request(
            "GET",
            f"{self.BASE_URL}/folder/list",
            params={"id": folder_id} if folder_id else None,
        )

    def delete_torrent(self, torrent_id):
        return self._make_request(
            "POST", f"{self.BASE_URL}/transfer/delete", data={"id": torrent_id}
        )

    def get_torrent_instant_availability(self, torrent_hashes: List[str]):
        results = self._make_request(
            "GET", f"{self.BASE_URL}/cache/check", params={"items[]": torrent_hashes}
        )
        if results.get("status") != "success":
            raise ProviderException(
                "Failed to get instant availability from Premiumize",
            )
        return results

    def get_available_torrent(
        self, info_hash: str, torrent_name
    ) -> Optional[Dict[str, Any]]:
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


class ProviderException(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)
