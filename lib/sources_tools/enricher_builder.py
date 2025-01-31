from typing import Dict, List
from .enricher import Enricher


class EnricherBuilder:
    def __init__(self, items: List[Dict]):
        self.items = [item.copy() for item in items]
        self._enrichers: List[Enricher] = []

    def add(self, enricher: Enricher) -> "EnricherBuilder":
        self._enrichers.append(enricher)
        return self

    def build(self) -> List[Dict]:
        processed = []
        for item in self.items:
            for enricher in self._enrichers:
                enricher.enrich(item)
            processed.append(item)
        return processed
