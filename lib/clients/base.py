from abc import ABC, abstractmethod
from typing import Any, Callable, List, Optional

from requests import Session
from requests.adapters import HTTPAdapter

try:
    from urllib3.util.retry import Retry
except ImportError:
    from requests.packages.urllib3.util.retry import Retry

from lib.domain.torrent import TorrentStream
from lib.utils.kodi.utils import notification


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
        exception_message = str(exception)
        if len(exception_message) > 70:
            exception_message = exception_message[:70] + "..."
        notification(exception_message)
