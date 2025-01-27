from json import JSONDecodeError
from requests.exceptions import RequestException, Timeout, TooManyRedirects
from requests import Session
from lib.utils.utils import USER_AGENT_HEADER
from lib.api.jacktook.kodi import kodilog


class Stremio:
    def __init__(self, authKey=None):
        self.authKey = authKey
        self.session = Session()
        self.session.headers.update(USER_AGENT_HEADER)

    def _request(self, method, url, data=None):
        try:
            if method == 'GET':
                resp = self.session.get(url, timeout=10)
            elif method == 'POST':
                resp = self.session.post(url, json=data, timeout=10)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            if resp.status_code != 200:
                kodilog(f"Status code {resp.status_code} received for URL: {url}. Response: {resp.text}")
                resp.raise_for_status()

            try:
                return resp.json()
            except JSONDecodeError:
                kodilog(f"Failed to decode JSON response for URL: {url}. Response: {resp.text}")
                raise
        except Timeout:
            kodilog(f"Request timed out for URL: {url}")
            raise
        except TooManyRedirects:
            kodilog(f"Too many redirects encountered for URL: {url}")
            raise
        except RequestException as e:
            kodilog(f"Failed to fetch data from {url}: {e}")
            raise

    def _get(self, url):
        return self._request('GET', url)

    def _post(self, url, data):
        return self._request('POST', url, data)

    def login(self, email, password):
        """Login to Stremio account."""

        data = {
            "authKey": self.authKey,
            "email": email,
            "password": password,
        }

        res = self._post("https://api.strem.io/api/login", data)
        self.authKey = res.get("result", {}).get("authKey", None)

    def dataExport(self):
        """Export user data."""
        assert self.authKey, "Login first"
        data = {"authKey": self.authKey}
        res = self._post("https://api.strem.io/api/dataExport", data)
        exportId = res.get("result", {}).get("exportId", None)

        dataExport = self._get(
            f"https://api.strem.io/data-export/{exportId}/export.json"
        )
        return dataExport

    def get_community_addons(self):
        """Get community addons."""
        response = self._get("https://stremio-addons.com/catalog.json")
        return response

    def get_my_addons(self):
        """Get user addons."""
        response = self.dataExport()
        return response.get("addons", {}).get("addons", [])
