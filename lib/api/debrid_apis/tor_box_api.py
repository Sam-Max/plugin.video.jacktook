from lib.api.debrid_apis.debrid_client import DebridClient, ProviderException
from lib.utils.kodi_utils import notification
from xbmcgui import DialogProgress
from lib.utils.kodi_utils import sleep as ksleep, dialogyesno


class Torbox(DebridClient):
    BASE_URL = "https://api.torbox.app/v1/api"

    def __init__(self, token=None):
        self.token = token
        self.initialize_headers()

    def initialize_headers(self):
        if self.token:
            self.headers = {"Authorization": f"Bearer {self.token}"}

    def _make_request(
        self,
        method,
        url,
        data=None,
        params=None,
        is_return_none=False,
        is_expected_to_fail=False,
    ):
        params = params or {}
        url = self.BASE_URL + url
        return super()._make_request(
            method, url, data, params, is_return_none, is_expected_to_fail
        )

    def add_magnet_link(self, magnet_link):
        return self._make_request(
            "POST",
            "/torrents/createtorrent",
            data={"magnet": magnet_link},
            is_expected_to_fail=False,
        )

    def get_user_torrent_list(self):
        return self._make_request("GET", "/torrents/mylist")

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

    def create_download_link(self, torrent_id, filename):
        response = self._make_request(
            "GET",
            "/torrents/requestdl",
            params={"token": self.token, "torrent_id": torrent_id, "file_id": filename},
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

    def download2(self, magnet, pack=False):
        cancelled = False
        TORBOX_ERROR_STATUS = ["failed"]
        self.add_magnet_link(magnet)
        ksleep(3000)
        progressDialog = DialogProgress()
        progressDialog.create("Cloud Transfer")
        while True:
            torrent_info = self.get_torrent_info(magnet)
            if torrent_info:
                torrent_id = torrent_info.get("id")
                status = torrent_info["download_state"]
                progress = torrent_info["progress"]
                if status == "metaDL":
                    progressDialog.update(int(progress), "Getting Metadata...")
                if status == "downloading":
                    while status == "downloading" and progress < 100:
                        msg = f"{status}...\n"
                        msg += f"Speed: {torrent_info['download_speed']}\n"
                        msg += f"ETA: {torrent_info['eta']}\n"
                        msg += f"Seeds:{torrent_info['seeds']}\n"
                        msg += f"Progress:{torrent_info['progress']}\n"
                        progress = torrent_info["progress"]
                        progressDialog.update(int(progress), msg)
                        if progressDialog.iscanceled():
                            cancelled = True
                            break
                        ksleep(5)
                        torrent_info = self.get_torrent_info(magnet)
                        print(torrent_info)
                        status = torrent_info["download_state"]
                        if any(x in status for x in TORBOX_ERROR_STATUS):
                            notification(f"Torbox Error. Status {status}")
                            break
                elif status == "completed" or cancelled is True:
                    break
        try:
            progressDialog.close()
        except Exception:
            pass
        ksleep(500)
        if cancelled:
            response = dialogyesno(
                "Kodi", "Do you want to continue the transfer in background?"
            )
            if response:
                pass
            else:
                self.delete_torrent(torrent_id)

    def delete_torrent(self, torrent_id):
        self._make_request(
            "POST",
            "/torrents/controltorrent",
            data={"torrent_id": torrent_id, "operation": "Delete"},
            is_expected_to_fail=False,
        )
