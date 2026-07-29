from json import JSONDecodeError

from requests import Session
from requests.exceptions import RequestException, Timeout, TooManyRedirects

from lib.utils.general.utils import USER_AGENT_HEADER
from lib.utils.kodi.settings import get_int_setting
from lib.utils.kodi.utils import kodilog


class Stremio:
    def __init__(self, authKey=None):
        self.authKey = authKey
        self.session = Session()
        self.session.headers.update(USER_AGENT_HEADER)

    def _request(self, method, url, data=None):
        try:
            if method == "GET":
                resp = self.session.get(url, timeout=get_int_setting("stremio_timeout"))
            elif method == "POST":
                resp = self.session.post(url, json=data, timeout=get_int_setting("stremio_timeout"))
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            if resp.status_code != 200:
                kodilog(f"Stremio API request failed: status={resp.status_code}")
                resp.raise_for_status()

            try:
                return resp.json()
            except JSONDecodeError:
                kodilog("Stremio API returned invalid JSON")
                raise
        except Timeout:
            kodilog("Stremio API request timed out")
            raise
        except TooManyRedirects:
            kodilog("Stremio API request exceeded redirect limit")
            raise
        except RequestException as e:
            kodilog(f"Stremio API request failed: {type(e).__name__}")
            raise

    def _get(self, url):
        return self._request("GET", url)

    def _post(self, url, data):
        return self._request("POST", url, data)

    def login(self, email, password):
        """Login to Stremio account."""
        data = {
            "authKey": self.authKey,
            "email": email,
            "password": password,
        }

        res = self._post("https://api.strem.io/api/login", data)
        self.authKey = res.get("result", {}).get("authKey", None)
        return self.authKey

    def dataExport(self):
        """Export user data."""
        assert self.authKey, "Login first"
        data = {"authKey": self.authKey}
        res = self._post("https://api.strem.io/api/dataExport", data)
        exportId = res.get("result", {}).get("exportId", None)

        dataExport = self._get(f"https://api.strem.io/data-export/{exportId}/export.json")
        return dataExport

    def get_my_addons(self):
        """Get user addons."""
        response = self.dataExport()
        return response.get("addons", {}).get("addons", [])
