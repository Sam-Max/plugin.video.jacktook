from .enricher import Enricher
import re
from re import Pattern
from typing import Dict


class IsPackEnricher(Enricher):
    def __init__(self, season_number: int):
        self.season_number = season_number
        self.season_fill = f"{season_number:02d}"
        self.pattern = self._build_pattern()

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

    def enrich(self, item: Dict) -> None:
        title = item.get("title", "")
        item["isPack"] = bool(self.pattern.search(title))
