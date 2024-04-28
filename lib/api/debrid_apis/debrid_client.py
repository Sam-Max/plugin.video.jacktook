from time import sleep
import traceback
import requests


class DebridClient:
    def __init__(self, token=None):
        self.token = token
        self.headers = {}
        self.initialize_headers()

    def _make_request(
        self,
        method,
        url,
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
        except requests.RequestException as error:
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
        except requests.JSONDecodeError as error:
            raise ProviderException(
                f"Failed to parse response error: {error}. \nresponse: {response.text}"
            )

    def initialize_headers(self):
        raise NotImplementedError

    def disable_access_token(self):
        raise NotImplementedError

    def wait_for_status(
        self,
        torrent_id,
        target_status,
        max_retries,
        retry_interval,
    ):
        """Wait for the torrent to reach a particular status."""
        retries = 0
        while retries < max_retries:
            torrent_info = self.get_torrent_info(torrent_id)
            if torrent_info["status"] == target_status:
                return torrent_info
            sleep(retry_interval)
            retries += 1
        raise ProviderException(
            f"Torrent not reach {target_status} status.",
        )

    def get_torrent_info(self, torrent_id):
        raise NotImplementedError


class ProviderException(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)
