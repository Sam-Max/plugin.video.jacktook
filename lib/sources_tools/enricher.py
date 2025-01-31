import abc
from typing import Dict


class Enricher(abc.ABC):
    @abc.abstractmethod
    def enrich(self, item: Dict) -> None:
        """Enrich an item with additional metadata"""
        pass
