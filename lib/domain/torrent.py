from dataclasses import dataclass, field
from typing import List


@dataclass
class TorrentStream:
    # Identification
    title: str = ""
    type: str = ""  # e.g., "torrent" or "debrid" or "direct"
    debridType: str = ""
    indexer: str = ""
    guid: str = ""
    infoHash: str = ""

    # Stats
    size: int = 0  # in bytes
    seeders: int = 0
    peers: int = 0

    # Language info
    languages: List[str] = field(default_factory=list)
    fullLanguages: str = ""

    # Source info
    provider: str = ""
    publishDate: str = ""  # ISO format preferred

    # Quality and URLs
    quality: str = "N/A"
    url: str = ""

    # Flags
    isPack: bool = False
    isCached: bool = False

