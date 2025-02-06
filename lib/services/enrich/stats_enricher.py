from lib.domain.interface.enricher_interface import EnricherInterface
from typing import Dict, Callable, List
import re
from lib.domain.source import Source

class StatsEnricher(EnricherInterface):
    def __init__(self, size_converter: Callable):
        self.size_pattern = re.compile(r"💾 ([\d.]+ (?:GB|MB))")
        self.seeders_pattern = re.compile(r"👤 (\d+)")
        self.provider_pattern = re.compile(r"([🌐🔗⚙️])\s*([^🌐🔗⚙️]+)")
        self.convert_size = size_converter
        
    def initialize(self, items: List[Source]) -> None:
        return

    def needs(self):
        return ["description"]

    def provides(self):
        return ["size", "seeders", "provider"]

    def enrich(self, item: Source) -> None:
        desc = item.get("description", "")
        if not desc:
            return

        # Size extraction
        if size_match := self.size_pattern.search(desc):
            item["size"] = self.convert_size(size_match.group(1))

        # Seeders extraction
        if seeders_match := self.seeders_pattern.search(desc):
            item["seeders"] = int(seeders_match.group(1))

        # Provider detection
        if provider_matches := self.provider_pattern.findall(desc):
            cleaned = [m[1].strip().splitlines()[0] for m in provider_matches]
            item["provider"] = cleaned[-1] if cleaned else "N/A"
