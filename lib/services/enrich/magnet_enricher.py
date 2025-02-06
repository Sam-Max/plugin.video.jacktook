from lib.domain.interface.enricher_interface import EnricherInterface
from typing import List
from lib.domain.source import Source

class MagnetEnricher(EnricherInterface):
    def __init__(self):
        pass

    def initialize(self, items: List[Source]) -> None:
        return

    def needs(self):
        return ["info_hash"]
    
    def provides(self):
        return ["magnet"]

    def enrich(self, item: Source) -> None:
        if "magnet" in item:
            return
        
        if "info_hash" not in item:
            return
        
        infoHash = item.get("info_hash")
        item["magnet"] = f"magnet:?xt=urn:btih:{infoHash}"