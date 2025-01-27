from abc import ABC, abstractmethod
from requests import Session


class BaseClient(ABC):
    def __init__(self, host, notification):
        self.host = host.rstrip("/") if host else ""
        self.notification = notification
        self.session = Session()

    @abstractmethod
    def search(self, tmdb_id, query, mode, media_type, season, episode):
        pass

    @abstractmethod
    def parse_response(self, res):
        pass

    def handle_exception(self, exception):
        exception_message = str(exception)
        if len(exception_message) > 70:
            exception_message = exception_message[:70] + "..."
        raise Exception(exception_message)

