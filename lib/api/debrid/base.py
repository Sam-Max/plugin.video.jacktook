import requests
import traceback
from abc import ABC, abstractmethod
from json.decoder import JSONDecodeError

from lib.utils.kodi.utils import kodilog, notification
from typing import Optional, Dict, Any


class DebridClient(ABC):
    """
    Abstract base class for Debrid service clients.
    Handles HTTP requests, error handling, and session management.
    """

    def __init__(
        self, token: str, timeout: int = 15, session: Optional[requests.Session] = None
    ):
        """
        Args:
            token (str): API token for authentication.
            timeout (int): Request timeout in seconds.
            session (requests.Session, optional): Custom session for requests.
        """
        self.token = token
        self.timeout = timeout
        self.session = session or requests.Session()
        self.headers = {}
        self.initialize_headers()

    def _make_request(
        self,
        method: str,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        is_return_none: bool = False,
        is_expected_to_fail: bool = False,
    ) -> Dict[str, Any]:
        """
        Make an HTTP request and handle errors.
        """
        response = self._perform_request(method, url, data, params, json)
        self._handle_errors(response, is_expected_to_fail)
        return self._parse_response(response, is_return_none)

    def _perform_request(
        self,
        method: str,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> requests.Response:
        """
        Perform the actual HTTP request.
        """
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
        except requests.exceptions.Timeout as e:
            kodilog(f"Timeout: {e}")
            raise ProviderException("Request timed out.")
        except requests.exceptions.ConnectionError as e:
            kodilog(f"ConnectionError: {e}")
            raise 
        except requests.exceptions.RequestException as e:
            kodilog(f"RequestException: {e}")
            raise ProviderException(f"Request failed: {str(e)}")
        except Exception as e:
            kodilog(f"Unexpected error: {e}")
            raise ProviderException(f"Unexpected error: {str(e)}")

    def _handle_errors(
        self, response: requests.Response, is_expected_to_fail: bool
    ) -> None:
        """
        Handle HTTP errors and raise ProviderException as needed.
        """
        try:
            response.raise_for_status()
        except requests.RequestException as error:
            status_code = getattr(error.response, "status_code", 0)
            url = getattr(error.response, "url", "Unknown URL")

            if is_expected_to_fail:
                return

            error_content = None
            content_type = response.headers.get("Content-Type", "")
            if content_type.startswith("application/json"):
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
                raise ProviderException("Invalid token", status_code, error_content)
            elif status_code == 403:
                raise ProviderException("Forbidden", status_code, error_content)
            elif status_code == 500:
                raise ProviderException(
                    "Internal server error", status_code, error_content
                )
            else:
                kodilog(
                    f"Error: {''.join(traceback.format_exception(type(error), error, error.__traceback__))}"
                )
                raise ProviderException(
                    f"API Error: {status_code} for {url}\nDetails: {error_content}",
                    status_code,
                    error_content,
                )

    @abstractmethod
    def initialize_headers(self) -> None:
        """
        Initialize headers for requests. Must be implemented by subclasses.
        """
        raise NotImplementedError

    @abstractmethod
    def disable_access_token(self):
        """
        Disable or revoke the access token. Must be implemented by subclasses.
        """
        raise NotImplementedError

    @staticmethod
    def _parse_response(
        response: requests.Response, is_return_none: bool
    ) -> Dict[str, Any]:
        """
        Parse the HTTP response as JSON.
        """
        if is_return_none:
            return {}
        try:
            return response.json()
        except JSONDecodeError as error:
            raise ProviderException(
                f"Failed to parse response error: {error}. \nresponse: {response.text}"
            )

    @abstractmethod
    def _handle_service_specific_errors(
        self, error_data: dict, status_code: int
    ) -> None:
        """
        Service specific errors on api requests. Must be implemented by subclasses.
        """
        raise NotImplementedError


class ProviderException(Exception):
    def __init__(
        self, message: str, status_code: Optional[int] = None, error_content: Any = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_content = error_content
        details = f"{self.message}"
        if self.status_code is not None:
            details += f" (Status code: {self.status_code})"
        if self.error_content is not None:
            details += f"\nError content: {self.error_content}"
        super().__init__(details)
        notification(details)
