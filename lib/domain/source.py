from typing import TypedDict, List, Any
from .cached_source import CachedSource


class Source(TypedDict, total=False):
    title: str
    description: str
    type: Any  # IndexerType
    url: str
    indexer: str
    guid: str
    magnet: str
    info_hash: str
    size: int
    languages: List[str]
    full_languages: List[str]
    provider: str
    publishDate: str
    seeders: int
    peers: int

    quality: str
    quality_sort: int

    status: str

    is_pack: bool
    is_cached: bool
    cache_sources: List[CachedSource]

    file: str
    folder: str

    correlative_id: int

    quality_formatted: str
    a1: str
    a2: str
    a3: str
    b1: str
    b2: str
    b3: str
