from .enricher import Enricher
import re
from typing import Dict, List


class QualityEnricher(Enricher):
    class ResolutionTier:
        def __init__(self, pattern: str, label: str, priority: int):
            self.regex = re.compile(pattern, re.IGNORECASE)
            self.label = label
            self.priority = priority

    def __init__(self):
        self.tiers = [
            self.ResolutionTier(
                r"(?i)\b(2160p?|4k)\b", "[B][COLOR yellow]4k[/COLOR][/B]", 4
            ),
            self.ResolutionTier(
                r"(?i)\b(1080p?)\b", "[B][COLOR blue]1080p[/COLOR][/B]", 3
            ),
            self.ResolutionTier(
                r"(?i)\b720p?\b", "[B][COLOR orange]720p[/COLOR][/B]", 2
            ),
            self.ResolutionTier(
                r"(?i)\b480p?\b", "[B][COLOR orange]480p[/COLOR][/B]", 1
            ),
        ]

    def initialize(self, items: List[Dict]) -> None:
        return

    def needs(self):
        return ["title"]
    
    def provides(self):
        return ["quality", "quality_sort"]

    def enrich(self, item: Dict) -> None:
        title = item.get("title", "")
        for tier in sorted(self.tiers, key=lambda t: -t.priority):
            if tier.regex.search(title):
                item["quality"] = tier.label
                item["quality_sort"] = tier.priority
                return

        item["quality"] = "[B][COLOR yellow]N/A[/COLOR][/B]"
        item["quality_sort"] = 0
