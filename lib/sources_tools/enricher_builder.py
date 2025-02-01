from typing import Dict, List
from .enricher import Enricher


class EnricherBuilder:
    def __init__(self):
        self._enrichers: List[Enricher] = []

    def add(self, enricher: Enricher) -> "EnricherBuilder":
        self._enrichers.append(enricher)
        return self

    def build(self, items: List[Dict]) -> List[Dict]:
        processed = []
        for enricher in self._enrichers:
            enricher.initialize(items)

        for item in [item.copy() for item in items]:
            for enricher in self._enrichers:
                enricher.enrich(item)
            processed.append(item)
        return processed
