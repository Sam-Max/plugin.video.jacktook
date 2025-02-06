import abc
from typing import List
from lib.domain.source import Source


class EnricherInterface(abc.ABC):
    @abc.abstractmethod
    def enrich(self, item: Source) -> None:
        """Enrich an item with additional metadata"""
        pass

    @abc.abstractmethod
    def initialize(self, items: List[Source]) -> None:
        """Initialize the enricher with a list of items"""
        pass

    @abc.abstractmethod
    def needs(self) -> List[str]:
        """Returns the fields that the enricher needs to function"""
        pass

    @abc.abstractmethod
    def provides(self) -> List[str]:
        """Returns the fields that the enricher will provide"""
        pass
