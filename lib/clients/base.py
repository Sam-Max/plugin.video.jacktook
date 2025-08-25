from abc import ABC, abstractmethod
from requests import Session
from typing import Any, List, Optional, Callable
from lib.domain.torrent import TorrentStream
from lib.utils.kodi.utils import notification


class BaseClient(ABC):
    def __init__(self, host: Optional[str], notification: Optional[Callable]) -> None:
        self.host = host.rstrip("/") if host else ""
        self.notification = notification
        self.session = Session()

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
