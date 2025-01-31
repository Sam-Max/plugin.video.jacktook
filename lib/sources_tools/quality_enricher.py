from .enricher import Enricher
import re
from typing import Dict


class QualityEnricher(Enricher):
    class ResolutionTier:
        def __init__(self, pattern: str, label: str, priority: int):
            self.regex = re.compile(pattern, re.IGNORECASE)
            self.label = label
            self.priority = priority

    def __init__(self, field_name: str = "quality"):
        self.field_name = field_name
        self.tiers = [
            self.ResolutionTier(
                r"(?i)\b(2160p?|4k|uhd)\b", "[B][COLOR yellow]4k[/COLOR][/B]", 4
            ),
            self.ResolutionTier(
                r"(?i)\b(1080p?|fullhd)\b", "[B][COLOR blue]1080p[/COLOR][/B]", 3
            ),
            self.ResolutionTier(
                r"(?i)\b720p?\b", "[B][COLOR orange]720p[/COLOR][/B]", 2
            ),
            self.ResolutionTier(
                r"(?i)\b480p?\b", "[B][COLOR orange]480p[/COLOR][/B]", 1
            ),
        ]

    def enrich(self, item: Dict) -> None:
        title = item.get("title", "")
        for tier in sorted(self.tiers, key=lambda t: -t.priority):
            if tier.regex.search(title):
                item["quality"] = tier.label
                item["quality_sort"] = tier.priority
                return

        item["quality"] = "[B][COLOR yellow]N/A[/COLOR][/B]"
        item["quality_sort"] = 0
