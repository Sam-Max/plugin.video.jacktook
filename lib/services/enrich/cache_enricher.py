from lib.domain.interface.enricher_interface import EnricherInterface
from typing import Dict, List
from lib.clients.debrid.debrid_client import ProviderException
from lib.domain.interface.cache_provider_interface import CacheProviderInterface
from lib.domain.cached_source import CachedSource
from lib.api.jacktook.kodi import kodilog
from lib.domain.source import Source


class CacheEnricher(EnricherInterface):
    def __init__(self, cache_providers: List[CacheProviderInterface]):
        self.cache_providers = cache_providers

    def initialize(self, items: List[Source]) -> None:
        self.provider_results: List[Dict[str, CachedSource]] = []

        for cache_provider in self.cache_providers:
            cached_hashes = cache_provider.get_cached_hashes(items)
            self.provider_results.append(cached_hashes)

        return

    def needs(self):
        return ["info_hash"]

    def provides(self):
        return ["is_cached", "cache_sources"]

    def enrich(self, item: Source) -> None:
        info_hash = item.get("info_hash")
        if not info_hash:
            return

        for provider_result in self.provider_results:
            cached_source = provider_result.get(info_hash)
            if not cached_source:
                continue

            item["is_cached"] = True
            item["cache_sources"] = list(
                item.get("cache_sources", []) + [cached_source]
            )
