import concurrent.futures
import re
from abc import ABC, abstractmethod
from typing import Any, Callable, List, Optional

import requests
from requests import Session
from requests.adapters import HTTPAdapter

try:
    from urllib3.util.retry import Retry
except ImportError:
    from requests.packages.urllib3.util.retry import Retry

import xbmc

from lib.domain.torrent import TorrentStream
from lib.utils.kodi.logging import kodilog
from lib.utils.kodi.utils import notification

_SECRET_QUERY_RE = re.compile(
    r"(?i)([?&](?:apikey|api_key|token|access_token|refresh_token|password|secret|key)=)"
    r"[^&\s'\"()<>,]+"
)


def _redact_secrets(message: str) -> str:
    """Hide credentials carried in URL query strings before logging."""
    return _SECRET_QUERY_RE.sub(r"\1***", message)


class BaseClient(ABC):
    def __init__(self, host: Optional[str], notification: Optional[Callable]) -> None:
        self.host = host.rstrip("/") if host else ""
        self.notification = notification
        self.session = Session()
        self.timeout = (5, 15)
        retry = Retry(
            total=2,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def safe_get(self, url: str, **kwargs: Any) -> Any:
        """``session.get`` with a real wall-clock deadline.

        ``requests``'s own ``timeout`` only bounds the gap between individual
        socket reads, not the request as a whole - a server that trickles
        data slowly enough (an anti-bot challenge holding the connection
        open, for instance) never trips it and can hang far past the
        caller's configured timeout. Enforce that same value as an actual
        deadline around the whole send+read instead, so a stalled response
        can't block the caller indefinitely. Uses whatever ``timeout`` the
        caller already passed in (falling back to ``self.timeout``) rather
        than a new hardcoded value.
        """
        deadline = kwargs.get("timeout", self.timeout)
        if isinstance(deadline, (tuple, list)):
            deadline = sum(deadline)
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(self.session.get, url, **kwargs)
        try:
            return future.result(timeout=deadline)
        except concurrent.futures.TimeoutError:
            raise requests.exceptions.Timeout(
                f"Request exceeded hard timeout of {deadline}s (stalled response)"
            )
        finally:
            executor.shutdown(wait=False)

    @abstractmethod
    def search(
        self,
        tmdb_id: str,
        query: str,
        mode: str,
        media_type: str,
        season: Optional[int],
        episode: Optional[int],
    ) -> List[TorrentStream]:
        pass

    @abstractmethod
    def parse_response(self, res: Any) -> List[TorrentStream]:
        pass

    def handle_exception(self, exception: str) -> None:
        exception_message = _redact_secrets(str(exception))
        # The notification is truncated; keep the full error in kodi.log for diagnostics.
        kodilog(f"{type(self).__name__} error: {exception_message}", level=xbmc.LOGERROR)
        if len(exception_message) > 70:
            exception_message = exception_message[:70] + "..."
        notification(exception_message)
