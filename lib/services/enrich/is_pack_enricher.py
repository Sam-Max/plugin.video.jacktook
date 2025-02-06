from lib.domain.interface.enricher_interface import EnricherInterface
import re
from re import Pattern
from typing import Dict, List
from lib.domain.source import Source

class IsPackEnricher(EnricherInterface):
    def __init__(self, season_number: int):
        self.season_number = season_number
        self.season_fill = f"{season_number:02d}"
        self.pattern = self._build_pattern()

    def initialize(self, items: List[Source]) -> None:
        return
    
    def needs(self):
        return ["title"]
    
    def provides(self):
        return ["isPack"]

    def _build_pattern(self) -> Pattern:
        base_patterns = [
            # Season number variations
            rf"\.S({self.season_number}|{self.season_fill})\.",
            rf"\sS({self.season_number}|{self.season_fill})\s",
            rf"\.({self.season_number}|{self.season_fill})\.season",
            # Complete season indicators
            r"total\.season",
            r"(^|\s)season(\s|$)",
            r"the\.complete",
            r"(^|\s)complete(\s|$)",
            # Episode range detection
            rf"S{self.season_fill}E\d{{2}}-\d{{2}}",
            # Season directory patterns
            rf"\.season\.({self.season_number}|{self.season_fill})\.",
            rf"\.season({self.season_number}|{self.season_fill})\.",
            # Season range patterns
            rf"s01 (to|thru) ({self.season_number}|s{self.season_fill})",
            rf"s1 (to|thru) ({self.season_number}|s{self.season_fill})",
        ]

        return re.compile(
            "|".join(f"({p})" for p in base_patterns), flags=re.IGNORECASE
        )

    def enrich(self, item: Source) -> None:
        title = item.get("title", "")
        item["is_pack"] = bool(self.pattern.search(title))
