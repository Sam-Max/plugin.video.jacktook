from lib.api.debrid.base import DebridClient, ProviderException
from base64 import b64encode, b64decode
from lib.utils.kodi.utils import (
    dialog_ok,
    kodilog,
    set_setting,
)
from lib.services.debrid.auth import run_realdebrid_auth
from lib.services.debrid.download import run_realdebrid_download


class RealDebrid(DebridClient):
    BASE_URL = "https://api.real-debrid.com/rest/1.0"
    OAUTH_URL = "https://api.real-debrid.com/oauth/v2"
    CLIENT_ID = "X245A4XAIBGVM"

    def initialize_headers(self):
        self.headers = {"User-Agent": "Jacktook/1.0"}
        if not self.token or not isinstance(self.token, str):
            kodilog("Invalid token")
            return
        token_data = self.decode_token_str(self.token)
        if "private_token" in token_data:
            self.headers["Authorization"] = f"Bearer {token_data['private_token']}"
        else:
            # Exchange client_id/secret/code for an access token
            access_token_data = self.get_token(
                token_data["client_id"],
                token_data["client_secret"],
                token_data["code"],
            )
            self.headers["Authorization"] = (
                f"Bearer {access_token_data['access_token']}"
            )

    def _handle_service_specific_errors(self, error_data: dict, status_code: int):
        error_code = error_data.get("error_code")
        messages = {
            -1: "Internal error",
            1: "Missing parameter",
            2: "Bad parameter value",
            3: "Unknown method",
            4: "Method not allowed",
            5: "Slow down",
            6: "Resource unreachable",
            7: "Resource not found",
            8: "Bad token",
            9: "Permission denied",
            10: "Two-Factor authentication needed",
            11: "Two-Factor authentication pending",
            12: "Invalid login",
            13: "Invalid password",
            14: "Account locked",
            15: "Account not activated",
            16: "Unsupported hoster",
            17: "Hoster in maintenance",
            18: "Hoster limit reached",
            19: "Hoster temporarily unavailable",
            20: "Hoster not available for free users",
            21: "Too many active downloads",
            22: "IP address not allowed",
            23: "Traffic exhausted",
            24: "File unavailable",
            25: "Service unavailable",
            26: "Upload too big",
            27: "Upload error",
            28: "File not allowed",
            29: "Torrent too big",
            30: "Torrent file invalid",
            31: "Action already done",
            32: "Image resolution error",
            33: "Torrent already active",
            34: "Too many requests",
            35: "Infringing file",
            36: "Fair Usage Limit",
            37: "Disabled endpoint",
        }

        if error_code in messages:
            raise ProviderException(messages[error_code])
        err = error_data.get("error") or error_data.get("message")
        if err:
            raise ProviderException(f"{err} (code {error_code})")
        raise ProviderException(f"Real-Debrid error (code {error_code})")

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

    @staticmethod
    def encode_token_data(client_id, client_secret, code):
        token = f"{client_id}:{client_secret}:{code}"
        return b64encode(str(token).encode()).decode()

    @staticmethod
    def decode_token_str(token):
        try:
            decoded = b64decode(token)
            decoded_str = decoded.decode()
            parts = decoded_str.split(":")
            if len(parts) != 3:
                raise ProviderException("Invalid token format")
            client_id, client_secret, code = parts
            return {
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
            }
        except Exception as e:
            raise ProviderException(f"Invalid token {e}")

    def get_device_code(self):
        return self._make_request(
            "GET",
            f"{self.OAUTH_URL}/device/code",
            params={"client_id": self.CLIENT_ID, "new_credentials": "yes"},
        )

    def get_token(self, client_id, client_secret, device_code):
        return self._make_request(
            "POST",
            f"{self.OAUTH_URL}/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": device_code,
                "grant_type": "http://oauth.net/grant_type/device/1.0",
            },
        )

    def authorize(self, device_code):
        response_data = self._make_request(
            "GET",
            f"{self.OAUTH_URL}/device/credentials",
            params={"client_id": self.CLIENT_ID, "code": device_code},
            is_expected_to_fail=True,
        )

        if "client_secret" not in response_data:
            return response_data

        token_data = self.get_token(
            response_data["client_id"], response_data["client_secret"], device_code
        )
        if "access_token" in token_data:
            token = self.encode_token_data(
                response_data["client_id"],
                response_data["client_secret"],
                token_data["refresh_token"],
            )
            return {"token": token}
        else:
            return token_data

    def remove_auth(self):
        self.token = ""
        set_setting("real_debrid_token", "")
        set_setting("real_debid_authorized", "false")
        set_setting("real_debrid_user", "")
        dialog_ok("Success", "Authentification Removed.")

    def auth(self):
        run_realdebrid_auth(self)

    def download(self, magnet_url, pack=False):
        run_realdebrid_download(self, magnet_url, pack=pack)

    def get_hosts(self):
        return self._make_request("GET", f"{self.BASE_URL}/hosts")

    def add_magnet_link(self, magnet_link):
        return self._make_request(
            "POST", f"{self.BASE_URL}/torrents/addMagnet", data={"magnet": magnet_link}
        )

    def get_user_torrent_list(self):
        return self._make_request("GET", f"{self.BASE_URL}/torrents")

    def get_user_downloads_list(self, page=1):
        return self._make_request(
            "GET", f"{self.BASE_URL}/downloads", params={"page": page}
        )

    def get_user(self):
        return self._make_request("GET", f"{self.BASE_URL}/user")

    def days_remaining(self):
        try:
            user = self.get_user()
            if not user or "expiration" not in user:
                return None

            expiration = user["expiration"]
            if not expiration:
                return None

            import datetime

            try:
                expires = datetime.datetime.strptime(
                    expiration, "%Y-%m-%dT%H:%M:%S.%fZ"
                )
            except ValueError:
                expires = datetime.datetime.strptime(expiration, "%Y-%m-%dT%H:%M:%SZ")

            days = (expires - datetime.datetime.utcnow()).days
            return days
        except Exception as e:
            kodilog(f"Error calculating RealDebrid days remaining: {e}")
            return None

    def get_torrent_active_count(self):
        return self._make_request("GET", f"{self.BASE_URL}/torrents/activeCount")

    def get_torrent_info(self, torrent_id):
        return self._make_request("GET", f"{self.BASE_URL}/torrents/info/{torrent_id}")

    def get_torrent_instant_availability(self, torrent_hash):
        return self._make_request(
            "GET", f"{self.BASE_URL}/torrents/instantAvailability/{torrent_hash}"
        )

    def disable_access_token(self):
        pass

    def select_files(self, torrent_id, file_ids="all"):
        return self._make_request(
            "POST",
            f"{self.BASE_URL}/torrents/selectFiles/{torrent_id}",
            data={"files": file_ids},
            is_return_none=True,
        )

    def get_available_torrent(self, info_hash):
        available_torrents = self.get_user_torrent_list()
        for torrent in available_torrents:
            if isinstance(torrent, dict) and torrent.get("hash") == info_hash:
                return torrent

    def create_download_link(self, link):
        response = self._make_request(
            "POST",
            f"{self.BASE_URL}/unrestrict/link",
            data={"link": link},
        )
        if "download" in response:
            return response

        if "error_code" in response:
            if response["error_code"] == 23:
                raise ProviderException("Exceed remote traffic limit")
        raise ProviderException(f"Failed to create download link. response: {response}")

    def delete_torrent(self, torrent_id):
        return self._make_request(
            "DELETE",
            f"{self.BASE_URL}/torrents/delete/{torrent_id}",
            is_return_none=True,
        )
