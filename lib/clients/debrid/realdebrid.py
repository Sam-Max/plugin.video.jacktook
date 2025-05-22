from time import time
from lib.clients.debrid.base import DebridClient, ProviderException
from base64 import b64encode, b64decode
from lib.utils.general.utils import supported_video_extensions
from lib.utils.kodi.utils import (
    copy2clip,
    dialog_ok,
    dialogyesno,
    notification,
    set_setting,
    progressDialog,
    sleep as ksleep,
)
from xbmcgui import DialogProgress


class RealDebrid(DebridClient):
    BASE_URL = "https://api.real-debrid.com/rest/1.0"
    OAUTH_URL = "https://api.real-debrid.com/oauth/v2"
    OPENSOURCE_CLIENT_ID = "X245A4XAIBGVM"

    def initialize_headers(self):
        if self.token:
            token_data = self.decode_token_str(self.token)
            if "private_token" in token_data:
                self.headers = {
                    "Authorization": f"Bearer {token_data['private_token']}"
                }
            else:
                access_token_data = self.get_token(
                    token_data["client_id"],
                    token_data["client_secret"],
                    token_data["code"],
                )
                self.headers = {
                    "Authorization": f"Bearer {access_token_data['access_token']}"
                }

    def _handle_service_specific_errors(self, error_data: dict, status_code: int):
        error_code = error_data.get("error_code")
        if error_code == 9:
            raise ProviderException("Real-Debrid Permission denied")
        elif error_code == 22:
            raise ProviderException("IP address not allowed")
        elif error_code == 34:
            raise ProviderException("Too many requests")
        elif error_code == 35:
            raise ProviderException("Content marked as infringing")
        elif error_code == 25:
            raise ProviderException("Service Unavailable")
        elif error_code == 21:
            raise ProviderException("Too many active downloads")
        elif error_code == 35:
            raise ProviderException("Infringing file")

    def __del__(self):
        if self.token:
            self.disable_access_token()

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
            client_id, client_secret, code = b64decode(token).decode().split(":")
        except ValueError as e:
            raise ProviderException(f"Invalid token {e}")
        return {"client_id": client_id, "client_secret": client_secret, "code": code}

    def get_device_code(self):
        return self._make_request(
            "GET",
            f"{self.OAUTH_URL}/device/code",
            params={"client_id": self.OPENSOURCE_CLIENT_ID, "new_credentials": "yes"},
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
            params={"client_id": self.OPENSOURCE_CLIENT_ID, "code": device_code},
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
        set_setting("real_debrid_token", "")
        set_setting("real_debid_authorized", "false")
        set_setting("real_debrid_user", "")
        dialog_ok("Success", "Authentification Removed.")

    def auth(self):
        response = self.get_device_code()
        if response:
            interval = int(response["interval"])
            expires_in = int(response["expires_in"])
            device_code = response["device_code"]
            user_code = response["user_code"]
            copy2clip(user_code)
            content = "%s[CR]%s[CR]%s" % (
                "Authorize Debrid Services",
                "Navigate to: [B]%s[/B]" % "https://real-debrid.com/device",
                "Enter the following code: [COLOR seagreen][B]%s[/B][/COLOR]"
                % user_code,
            )
            progressDialog.create("Real-Debrid Auth")
            progressDialog.update(-1, content)
            start_time = time()
            while time() - start_time < expires_in:
                try:
                    response = self.authorize(device_code)
                    if "token" in response:
                        progressDialog.close()
                        set_setting("real_debrid_token", response["token"])
                        set_setting("real_debid_authorized", "true")
                        self.token = response["token"]
                        self.initialize_headers()
                        set_setting("real_debrid_user", self.get_user()["username"])
                        dialog_ok("Success", "Authentication completed.")
                        return
                    if progressDialog.iscanceled():
                        progressDialog.close()
                        return
                    ksleep(1000 * interval)
                except Exception as e:
                    dialog_ok("Error:", f"Error: {e}.")
                    return

    def download(self, magnet_url, pack=False):
        interval = 5
        cancelled = False
        DEBRID_ERROR_STATUS = ("magnet_error", "error", "virus", "dead")
        response = self.add_magnet_link(magnet_url)
        if response:
            torrent_id = response["id"]
            progressDialog = DialogProgress()
            torrent_info = self.get_torrent_info(torrent_id)
            if torrent_info:
                status = torrent_info["status"]
                if status == "magnet_conversion":
                    msg = "Converting Magnet...\n\n"
                    msg += torrent_info["filename"]
                    progress_timeout = 100
                    progressDialog.create("Cloud Transfer")
                    while status == "magnet_conversion" and progress_timeout > 0:
                        progressDialog.update(progress_timeout, msg)
                        if progressDialog.iscanceled():
                            cancelled = True
                            break
                        progress_timeout -= interval
                        ksleep(1000 * interval)
                        torrent_info = self.get_torrent_info(torrent_id)
                        status = torrent_info["status"]
                        if any(x in status for x in DEBRID_ERROR_STATUS):
                            notification("Real Debrid Error.")
                            break
        elif status == "downloaded":
            notification("File already cached")
            return
        elif status == "waiting_files_selection":
            files = torrent_info["files"]
            extensions = supported_video_extensions()[:-1]
            items = [
                item
                for item in files
                for x in extensions
                if item["path"].lower().endswith(x)
            ]
            try:
                video = max(items, key=lambda x: x["bytes"])
                file_id = video["id"]
            except ValueError as e:
                notification(e)
                return
            self.select_files(torrent_id, str(file_id))
            ksleep(2000)
            torrent_info = self.get_torrent_info(torrent_id)
            if torrent_info:
                status = torrent_info["status"]
                if status == "downloaded":
                    notification("File cached")
                    return
                file_size = round(float(video["bytes"]) / (1000**3), 2)
                msg = "Saving File to the Real Debrid Cloud...\n"
                msg += f"{torrent_info['filename']}\n\n"
                progressDialog.create("Cloud Transfer")
                progressDialog.update(1, msg)
                while not status == "downloaded":
                    ksleep(1000 * interval)
                    torrent_info = self.get_torrent_info(torrent_id)
                    status = torrent_info["status"]
                    if status == "downloading":
                        msg2 = (
                            "Downloading %s GB @ %s mbps from %s peers, %s %% completed"
                            % (
                                file_size,
                                round(float(torrent_info["speed"]) / (1000**2), 2),
                                torrent_info["seeders"],
                                torrent_info["progress"],
                            )
                        )
                    else:
                        msg2 = status
                    progressDialog.update(
                        int(float(torrent_info["progress"])), msg + msg2
                    )
                    try:
                        if progressDialog.iscanceled():
                            cancelled = True
                            break
                    except Exception:
                        pass
                    if any(x in status for x in DEBRID_ERROR_STATUS):
                        notification("Real Debrid Error.")
                        break
        try:
            progressDialog.close()
        except Exception:
            pass
        ksleep(500)
        if cancelled:
            response = dialogyesno(
                "Kodi", "Do you want to continue transfer in background?"
            )
            if response:
                notification("Saving file to the Real Debrid Cloud")
            else:
                self.delete_torrent(torrent_id)

    def get_hosts(self):
        return self._make_request("GET", f"{self.BASE_URL}/hosts")

    def add_magnet_link(self, magnet_link):
        return self._make_request(
            "POST", f"{self.BASE_URL}/torrents/addMagnet", data={"magnet": magnet_link}
        )

    def add_torrent_file(self, file):
        return self._make_request(
            "PUT", f"{self.BASE_URL}/torrents/addTorrent", file=file
        )

    def get_user_torrent_list(self):
        return self._make_request("GET", f"{self.BASE_URL}/torrents")

    def get_user_downloads_list(self, page=1):
        return self._make_request(
            "GET", f"{self.BASE_URL}/downloads", params={"page": page}
        )

    def get_user(self):
        return self._make_request("GET", f"{self.BASE_URL}/user")

    def get_torrent_active_count(self):
        return self._make_request("GET", f"{self.BASE_URL}/torrents/activeCount")

    def get_torrent_info(self, torrent_id):
        return self._make_request("GET", f"{self.BASE_URL}/torrents/info/{torrent_id}")

    def get_torrent_instant_availability(self, torrent_hash):
        return self._make_request(
            "GET", f"{self.BASE_URL}/torrents/instantAvailability/{torrent_hash}"
        )

    def disable_access_token(self):
        return self._make_request(
            "GET", f"{self.BASE_URL}/disable_access_token", is_return_none=True
        )

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
            if torrent["hash"] == info_hash:
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

