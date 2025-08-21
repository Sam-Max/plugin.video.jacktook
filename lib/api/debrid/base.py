import requests
import traceback
from abc import ABC, abstractmethod
from json.decoder import JSONDecodeError

from lib.utils.kodi.utils import kodilog, notification


class DebridClient(ABC):
    def __init__(self, token, timeout=15):
        self.headers = {}
        self.token = token
        self.timeout = timeout
        self.session = requests.Session()  # reuse session
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
            return self.session.request(
                method=method,
                url=url,
                params=params,
                data=data,
                json=json,
                headers=self.headers,
                timeout=self.timeout,
            )
        except requests.exceptions.Timeout:
            raise ProviderException("Request timed out.")
        except requests.exceptions.ConnectionError:
            raise ProviderException("Failed to connect to Debrid service.")
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Request failed: {str(e)}")

    def _handle_errors(self, response, is_expected_to_fail):
        try:
            response.raise_for_status()
        except requests.RequestException as error:
            if is_expected_to_fail:
                kodilog(f"Expected failure: {error}")
                return

            status_code = getattr(error.response, "status_code", None)
            url = getattr(error.response, "url", "Unknown URL")

            error_content = None
            if response.headers.get("Content-Type", "").startswith("application/json"):
                try:
                    error_content = response.json()
                except ValueError:
                    error_content = response.text
            else:
                error_content = response.text

            # Call service-specific error hook if JSON
            if isinstance(error_content, dict):
                self._handle_service_specific_errors(error_content, status_code)

            # Specific cases
            if status_code == 401:
                raise ProviderException("Invalid token")
            elif status_code == 403:
                raise ProviderException("Forbidden")
            elif status_code == 500:
                raise ProviderException("Internal server error")

            formatted_traceback = "".join(
                traceback.format_exception(type(error), error, error.__traceback__)
            )
            kodilog(f"Error: {formatted_traceback}")

            raise ProviderException(
                f"API Error: {status_code} for {url}\nDetails: {error_content}"
            )

    @abstractmethod
    def initialize_headers(self):
        raise NotImplementedError

    @abstractmethod
    def disable_access_token(self):
        raise NotImplementedError

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

    @abstractmethod
    def _handle_service_specific_errors(self, error_data: dict, status_code):
        """
        Service specific errors on api requests.
        """
        raise NotImplementedError


class ProviderException(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)
        notification(self.message)
