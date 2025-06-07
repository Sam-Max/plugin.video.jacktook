from abc import ABC, abstractmethod
from requests import Session
from typing import List, Optional
from lib.domain.torrent import TorrentStream


class BaseClient(ABC):
    def __init__(self, host: Optional[str], notification: Optional[callable]) -> None:
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
    def parse_response(self, res: any) -> List[TorrentStream]:
        pass

    def handle_exception(self, exception: Exception) -> None:
        exception_message = str(exception)
        if len(exception_message) > 70:
            exception_message = exception_message[:70] + "..."
        raise Exception(exception_message)
