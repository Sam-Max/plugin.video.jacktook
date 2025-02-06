from abc import ABC, abstractmethod
from typing import List, Dict
from lib.domain.cached_source import CachedSource
from lib.domain.source import Source


class CacheProviderInterface(ABC):
    @abstractmethod
    def get_cached_hashes(self, infoHashes: List[Source]) -> Dict[str, CachedSource]:
        pass
