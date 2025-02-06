from lib.domain.interface.enricher_interface import EnricherInterface
from lib.domain.quality_tier import QualityTier
from typing import List
from lib.domain.source import Source

class QualityEnricher(EnricherInterface):
    def __init__(self):
        self.tiers = QualityTier.default_quality_tiers()

    def initialize(self, items: List[Source]) -> None:
        return

    def needs(self):
        return ["title"]
    
    def provides(self):
        return ["quality", "quality_sort", "quality_formatted"]

    def enrich(self, item: Source) -> None:
        title = item.get("title", "")
        for tier in sorted(self.tiers, key=lambda t: -t.priority):
            if tier.regex is None or tier.regex.search(title):
                item["quality"] = tier.label
                item["quality_formatted"] = tier.label_formatted
                item["quality_sort"] = tier.priority
                return
