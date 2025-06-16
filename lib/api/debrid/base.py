from abc import abstractmethod
import traceback
import requests
from abc import ABC, abstractmethod
from lib.utils.kodi.utils import kodilog, notification


class DebridClient(ABC):
    def __init__(self, token):
        self.headers = {}
        self.token = token
        self.initialize_headers()

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
        response = self._perform_request(method, url, data, params, json)
        self._handle_errors(response, is_expected_to_fail)
        return self._parse_response(response, is_return_none)

    def _perform_request(self, method, url, data, params, json):
        try:
            return requests.Session().request(
                method,
                url,
                params=params,
                data=data,
                json=json,
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

            if response.headers.get("Content-Type") == "application/json":
                error_content = response.json()
                self._handle_service_specific_errors(
                    error_content, error.response.status_code
                )
            else:
                error_content = response.text()

            if error.response.status_code == 401:
                raise ProviderException("Invalid token")

            if error.response.status_code == 403:
                raise ProviderException("Forbidden")

            formatted_traceback = "".join(traceback.format_exception(error))

            kodilog(formatted_traceback)
            kodilog(error_content)
            kodilog(error.response.status_code)

            raise ProviderException(f"API Error: {error_content}")

    @abstractmethod
    async def initialize_headers(self):
        raise NotImplementedError

    @abstractmethod
    async def disable_access_token(self):
        raise NotImplementedError

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

    @abstractmethod
    def _handle_service_specific_errors(self, error_data: dict, status_code: int):
        """
        Service specific errors on api requests.
        """
        raise NotImplementedError


class ProviderException(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)
        notification(self.message)
        
