from abc import ABC, abstractmethod
from requests import Session


class BaseClient(ABC):
    def __init__(self, host, notification):
        self.host = host.rstrip("/")
        self.notification = notification
        self.session = Session()

    @abstractmethod
    def search(self, tmdb_id, query, mode, media_type, season, episode):
        pass

    @abstractmethod
    def parse_response(self, res):
        pass

