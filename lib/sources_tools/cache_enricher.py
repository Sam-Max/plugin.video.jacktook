from .enricher import Enricher
from typing import Dict, Callable, List
import re
from lib.clients.debrid.torbox import Torbox
from lib.api.jacktook.kodi import kodilog

class CacheEnricher(Enricher):
    def __init__(self):
        pass
        
    def initialize(self, items: List[Dict]) -> None:
        infoHashes: List[str] = list(set(filter(None, [item.get("infoHash") for item in items])))
        
        torbox = Torbox("782153a0-dd26-4865-8f77-91f1dc9b78be")
        
        response = torbox.get_torrent_instant_availability(infoHashes)
        response.get('data', [])
        
        self.cachedHashes = set(response.get('data', []))
        kodilog(f"CacheEnricher: Cached hashes: {self.cachedHashes}")
        
    def needs(self):
        return ["infoHash"]

    def provides(self):
        return ["isCached", "status"]

    def enrich(self, item: Dict) -> None:
        if item.get("infoHash") in self.cachedHashes:
            item["isCached"] = True
            item["status"] = "Cached in Torbox"
            item["cachedIn"] = list(set(item.get("cachedIn", []) + ["Torbox"]))