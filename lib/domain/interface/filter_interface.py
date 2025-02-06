from abc import ABC, abstractmethod
from typing import Dict, Any
from lib.domain.source import Source


class FilterInterface(ABC):
    @abstractmethod
    def matches(self, item: Source) -> bool:
        pass

    def reset(self):
        pass
