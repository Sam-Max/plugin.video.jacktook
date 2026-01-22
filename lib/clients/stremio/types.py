from typing import List, Optional, Any, Dict, Union
from dataclasses import dataclass, field

@dataclass
class MetaLink:
    name: str
    category: str
    url: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MetaLink':
        return cls(
            name=data.get("name", ""),
            category=data.get("category", ""),
            url=data.get("url", "")
        )

@dataclass
class StreamBehaviorHints:
    countryWhitelist: List[str] = field(default_factory=list)
    notWebReady: bool = False
    bingeGroup: Optional[str] = None
    proxyHeaders: Dict[str, str] = field(default_factory=dict)
    videoHash: Optional[str] = None
    videoSize: Optional[int] = None
    filename: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StreamBehaviorHints':
        return cls(
            countryWhitelist=data.get("countryWhitelist", []),
            notWebReady=data.get("notWebReady", False),
            bingeGroup=data.get("bingeGroup"),
            proxyHeaders=data.get("proxyHeaders", {}),
            videoHash=data.get("videoHash"),
            videoSize=data.get("videoSize"),
            filename=data.get("filename")
        )

@dataclass
class Stream:
    url: Optional[str] = None
    ytId: Optional[str] = None
    infoHash: Optional[str] = None
    fileIdx: Optional[int] = None
    externalUrl: Optional[str] = None
    name: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    behaviorHints: Optional[StreamBehaviorHints] = None
    
    # Custom/Extended fields
    fileMustInclude: Optional[List[str]] = None
    nzbUrl: Optional[str] = None
    servers: List[str] = field(default_factory=list)
    rarUrls: List[str] = field(default_factory=list)
    zipUrls: List[str] = field(default_factory=list)
    sevenZipUrls: List[str] = field(default_factory=list)
    tgzUrls: List[str] = field(default_factory=list)
    tarUrls: List[str] = field(default_factory=list)
    
    meta: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Stream':
        hints = data.get("behaviorHints")
        return cls(
            url=data.get("url"),
            ytId=data.get("ytId"),
            infoHash=data.get("infoHash"),
            fileIdx=data.get("fileIdx"),
            externalUrl=data.get("externalUrl"),
            name=data.get("name"),
            title=data.get("title"),
            description=data.get("description"),
            behaviorHints=StreamBehaviorHints.from_dict(hints) if hints else None,
            fileMustInclude=data.get("fileMustInclude"),
            nzbUrl=data.get("nzbUrl"),
            servers=data.get("servers", []),
            rarUrls=data.get("rarUrls", []),
            zipUrls=data.get("zipUrls", []),
            sevenZipUrls=data.get("7zipUrls", []),
            tgzUrls=data.get("tgzUrls", []),
            tarUrls=data.get("tarUrls", []),
            meta=data.get("meta", {})
        )

    def get_parsed_title(self) -> str:
        filename = self.behaviorHints.filename if self.behaviorHints else None
        title = filename or self.description or self.title
        return title.splitlines()[0] if title else ""
    
    def get_sub_indexer(self, addon: Any) -> str:
        if addon.manifest.name.split(" ")[0] == "AIOStreams":
            return self.name.split()[1] if self.name else ""
        return ""
        
    def get_parsed_size(self) -> int:
        size = self.behaviorHints.videoSize if self.behaviorHints else None
        return size or self.meta.get("size") or 0
    
    def get_provider(self) -> str: 
        return self.meta.get("indexer") or ""

@dataclass
class Video:
    id: str
    title: str
    released: str
    thumbnail: Optional[str] = None
    streams: List[Stream] = field(default_factory=list)
    available: bool = False
    episode: Optional[int] = None
    season: Optional[int] = None
    trailers: List[Stream] = field(default_factory=list)
    overview: Optional[str] = None
    imdbSeason: Optional[Union[int, str]] = None
    imdbEpisode: Optional[Union[int, str]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Video':
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            released=data.get("released", ""),
            thumbnail=data.get("thumbnail"),
            streams=[Stream.from_dict(s) for s in data.get("streams", [])],
            available=data.get("available", False),
            episode=data.get("episode"),
            season=data.get("season"),
            trailers=[Stream.from_dict(t) for t in data.get("trailers", [])],
            overview=data.get("overview"),
            imdbSeason=data.get("imdbSeason"),
            imdbEpisode=data.get("imdbEpisode")
        )

@dataclass
class MetaBehaviorHints:
    defaultVideoId: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MetaBehaviorHints':
        return cls(defaultVideoId=data.get("defaultVideoId"))

@dataclass
class Meta:
    id: str
    type: str
    name: str
    poster: Optional[str] = None
    posterShape: Optional[str] = None
    background: Optional[str] = None
    logo: Optional[str] = None
    description: Optional[str] = None
    releaseInfo: Optional[str] = None
    director: List[str] = field(default_factory=list)
    cast: List[str] = field(default_factory=list)
    imdbRating: Optional[str] = None
    released: Optional[str] = None
    trailers: List[Dict[str, str]] = field(default_factory=list) # simplified for now
    links: List[MetaLink] = field(default_factory=list)
    videos: List[Video] = field(default_factory=list)
    runtime: Optional[str] = None
    language: Optional[str] = None
    country: Optional[str] = None
    awards: Optional[str] = None
    website: Optional[str] = None
    behaviorHints: Optional[MetaBehaviorHints] = None
    moviedb_id: Optional[str] = None
    imdb_id: Optional[str] = None
    genres: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Meta':
        hints = data.get("behaviorHints")
        return cls(
            id=data.get("id", ""),
            type=data.get("type", ""),
            name=data.get("name", ""),
            poster=data.get("poster"),
            posterShape=data.get("posterShape"),
            background=data.get("background"),
            logo=data.get("logo"),
            description=data.get("description"),
            releaseInfo=data.get("releaseInfo"),
            director=data.get("director", []),
            cast=data.get("cast", []),
            imdbRating=data.get("imdbRating"),
            released=data.get("released"),
            trailers=data.get("trailers", []),
            links=[MetaLink.from_dict(l) for l in data.get("links", [])],
            videos=[Video.from_dict(v) for v in data.get("videos", [])],
            runtime=data.get("runtime"),
            language=data.get("language"),
            country=data.get("country"),
            awards=data.get("awards"),
            website=data.get("website"),
            behaviorHints=MetaBehaviorHints.from_dict(hints) if hints else None,
            moviedb_id=data.get("moviedb_id"),
            imdb_id=data.get("imdb_id"),
            genres=data.get("genres", [])
        )


@dataclass
class MetaPreview:
    id: str
    type: str
    name: str
    poster: str
    posterShape: Optional[str] = None
    background: Optional[str] = None
    genres: List[str] = field(default_factory=list)
    imdbRating: Optional[str] = None
    releaseInfo: Optional[str] = None
    director: List[str] = field(default_factory=list)
    cast: List[str] = field(default_factory=list)
    links: List[MetaLink] = field(default_factory=list)
    description: Optional[str] = None
    trailers: List[Dict[str, str]] = field(default_factory=list)
    moviedb_id: Optional[str] = None
    imdb_id: Optional[str] = None
    streams: List[Stream] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MetaPreview':
        return cls(
            id=data.get("id", ""),
            type=data.get("type", ""),
            name=data.get("name", ""),
            poster=data.get("poster", ""),
            posterShape=data.get("posterShape"),
            background=data.get("background"),
            genres=data.get("genres", []),
            imdbRating=data.get("imdbRating"),
            releaseInfo=data.get("releaseInfo"),
            director=data.get("director", []),
            cast=data.get("cast", []),
            links=[MetaLink.from_dict(l) for l in data.get("links", [])],
            description=data.get("description"),
            trailers=data.get("trailers", []),
            moviedb_id=data.get("moviedb_id"),
            imdb_id=data.get("imdb_id"),
            streams=[Stream.from_dict(s) for s in data.get("streams", [])]
        )
