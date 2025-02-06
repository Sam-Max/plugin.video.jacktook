from typing import TypedDict, Any, List


class CachedSource(TypedDict):
    hash: str
    cache_provider: Any
    cache_provider_name: str
    ratio: float
    instant_availability: bool
    urls: List[str]
    playable_url: str
