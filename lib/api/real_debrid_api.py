from time import time
from lib.utils.kodi import sleep as ksleep
from base64 import b64encode, b64decode
import requests
from requests import ConnectionError
from lib.utils.kodi import (
    copy2clip,
    dialog_ok,
    dialogyesno,
    notify,
    set_setting,
    progressDialog,
)
from lib.utils.utils import supported_video_extensions
from xbmcgui import DialogProgress

# Source: https://github.com/mhdzumair/MediaFusion/blob/main/streaming_providers/realdebrid/client.py
# Modified to add func add_torrent_file, get_user_downloads_list


class RealDebrid:
    BASE_URL = "https://api.real-debrid.com/rest/1.0"
    OAUTH_URL = "https://api.real-debrid.com/oauth/v2"
    OPENSOURCE_CLIENT_ID = "X245A4XAIBGVM"

    def __init__(self, encoded_token=None):
        self.encoded_token = encoded_token
        self.headers = {}
        self.initialize_headers()

    def __del__(self):
        if self.encoded_token:
            self.disable_access_token()

    def _make_request(
        self,
        method,
        url,
        data=None,
        file=None,
        params=None,
        is_return_none=False,
    ):
        try:
            if method == "GET":
                response = requests.get(url, params=params, headers=self.headers)
            elif method == "POST":
                response = requests.post(url, data=data, headers=self.headers)
            elif method == "DELETE":
                response = requests.delete(url, headers=self.headers)
            elif method == "PUT":
                response = requests.put(url, data=file, headers=self.headers)

            if response.status_code == 401:
                notify("Invalid token")
                return
            elif (
                response.status_code == 403
                and response.json().get("error_code") == 9
            ):
                notify("Real-Debrid Permission denied for free account")
                return

            if is_return_none:
                return {}

            return response.json()
        except ConnectionError:
            notify("No network connection")
        except Exception as err:
            notify(f"Error: {str(err)}")

    def initialize_headers(self):
        if self.encoded_token:
            token_data = self.decode_token_str(self.encoded_token)
            access_token_data = self.get_token(
                token_data["client_id"], token_data["client_secret"], token_data["code"]
            )
            if access_token_data:
                self.headers = {
                    "Authorization": f"Bearer {access_token_data['access_token']}"
                }

    @staticmethod
    def encode_token_data(client_id, client_secret, code):
        token = f"{client_id}:{client_secret}:{code}"
        return b64encode(str(token).encode()).decode()

    @staticmethod
    def decode_token_str(token):
        try:
            client_id, client_secret, code = b64decode(token).decode().split(":")
        except ValueError:
            raise ProviderException("Invalid token")
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
        )
        if response_data:
            if "client_secret" not in response_data:
                return response_data
            token_data = self.get_token(
                response_data["client_id"], response_data["client_secret"], device_code
            )
            if token_data:
                if "access_token" in token_data:
                    token = self.encode_token_data(
                        response_data["client_id"],
                        response_data["client_secret"],
                        token_data["refresh_token"],
                    )
                    return {"token": token}
                else:
                    return token_data

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
                "Enter the following code: [COLOR seagreen][B]%s[/B][/COLOR]" % user_code,
            )
            progressDialog.create("Real-Debrid Auth")
            progressDialog.update(-1, content)
            start_time = time()
            while time() - start_time < expires_in:
                try:
                    response = self.authorize(device_code)
                    if response:
                        if "token" in response:
                            progressDialog.close()
                            set_setting("real_debrid_token", response["token"])
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
        response = self.add_magent_link(magnet_url)
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
                            notify("Real Debrid Error.")
                            break
        elif status == "downloaded":
            notify("File already cached")
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
                notify(e)
                return
            self.select_files(torrent_id, str(file_id))
            ksleep(2000)
            torrent_info = self.get_torrent_info(torrent_id)
            if torrent_info: 
                status = torrent_info["status"]
                if status == "downloaded":
                    notify("File cached")
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
                    progressDialog.update(int(float(torrent_info["progress"])), msg + msg2)
                    try:
                        if progressDialog.iscanceled():
                            cancelled = True
                            break
                    except Exception:
                        pass
                    if any(x in status for x in DEBRID_ERROR_STATUS):
                        notify("Real Debrid Error.")
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
                notify("Saving file to the Real Debrid Cloud")
            else:
                self.delete_torrent(torrent_id)

    def get_hosts(self):
        return self._make_request("GET", f"{self.BASE_URL}/hosts")

    def add_magent_link(self, magnet_link):
        return self._make_request(
            "POST", f"{self.BASE_URL}/torrents/addMagnet", data={"magnet": magnet_link}
        )

    def add_torrent_file(self, file):
        return self._make_request(
            "PUT", f"{self.BASE_URL}/torrents/addTorrent", file=file
        )

    def get_user_torrent_list(self, limit):
        return self._make_request(
            "GET", f"{self.BASE_URL}/torrents", params={"limit": limit}
        )

    def get_user_downloads_list(self, page, limit):
        return self._make_request(
            "GET", f"{self.BASE_URL}/downloads", params={"page": page, "limit": limit}
        )

    def get_user(self):
        return self._make_request("GET", f"{self.BASE_URL}/user")

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


class ProviderException(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)
