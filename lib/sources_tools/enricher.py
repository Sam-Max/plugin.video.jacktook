import abc
from typing import Dict, List


class Enricher(abc.ABC):
    @abc.abstractmethod
    def enrich(self, item: Dict) -> None:
        """Enrich an item with additional metadata"""
        pass

    @abc.abstractmethod
    def initialize(self, items: List[Dict]) -> None:
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