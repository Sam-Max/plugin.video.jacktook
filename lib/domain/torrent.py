from dataclasses import dataclass


@dataclass
class TorrentStream:
    title: str
    type: str
    indexer: str
    guid: str
    infoHash: str
    size: int
    seeders: int
    languages: list
    fullLanguages: str
    provider: str
    publishDate: str
    peers: int
    quality: str = "N/A"
    url: str = ""
    isPack: bool = False
    isCached: bool = False
