"""Safe normalization and resolution contracts for Stremio playback sources."""

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple
from urllib.parse import parse_qs, quote, unquote, urlparse

_HASH_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_DISPLAY_METADATA_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_HEADER_NAME_RE = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
_YOUTUBE_ADDON_ID = "plugin.video.youtube"


@dataclass
class StremioPlaybackCandidate:
    """Normalized, untrusted Stremio playback metadata."""

    url: Optional[str] = None
    ytId: Optional[str] = None
    infoHash: Optional[str] = None
    fileIdx: Optional[int] = None
    externalUrl: Optional[str] = None
    title: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    filename: Optional[str] = None
    size: Optional[int] = None
    videoHash: Optional[str] = None
    subtitles: List[Dict[str, Any]] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    trackers: List[str] = field(default_factory=list)
    headers: Dict[str, Any] = field(default_factory=dict)
    responseHeaders: Dict[str, Any] = field(default_factory=dict)
    fileMustInclude: Optional[List[str]] = None
    nzbUrl: Optional[str] = None
    archiveUrls: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    origin: str = ""

    @property
    def yt_id(self) -> Optional[str]:
        return self.ytId

    @property
    def info_hash(self) -> Optional[str]:
        return self.infoHash

    @property
    def file_idx(self) -> Optional[int]:
        return self.fileIdx

    @property
    def external_url(self) -> Optional[str]:
        return self.externalUrl

    @property
    def proxy_headers(self) -> Dict[str, Any]:
        return self.headers

    @property
    def stream_subtitles(self) -> List[Dict[str, Any]]:
        return self.subtitles


@dataclass(frozen=True)
class Decision:
    """Classification result produced before any playable URL is created."""

    source_class: str
    supported: bool
    reason: str = ""
    code: str = ""

    @property
    def kind(self) -> str:
        return self.source_class


class StremioPlaybackError(Exception):
    """Safe, user-facing failure that never includes a locator or credential."""

    def __init__(self, code: str, user_message: str):
        self.code = code
        self.user_message = _safe_message(user_message)
        super().__init__(self.user_message)


def normalize_stream(raw: Any, origin: str = "") -> StremioPlaybackCandidate:
    """Normalize a Stremio stream, cached source, or dictionary payload."""
    if isinstance(raw, StremioPlaybackCandidate):
        return raw

    values = _as_mapping(raw)
    metadata = _mapping_value(values, "stremioMetadata", "stremio_metadata")
    merged = dict(metadata) if isinstance(metadata, Mapping) else {}
    merged.update(values)
    behavior_hints = _mapping_value(merged, "behaviorHints", "behavior_hints")
    behavior_hints = _as_mapping(behavior_hints)

    proxy_headers = _mapping_value(behavior_hints, "proxyHeaders", "proxy_headers")
    if proxy_headers is None:
        proxy_headers = _mapping_value(merged, "proxyHeaders", "proxy_headers", "headers")
    request_headers, response_headers = _split_headers(proxy_headers)

    subtitles = _normalize_subtitles(
        _mapping_value(merged, "subtitles", "streamSubtitles", "stream_subtitles")
    )
    filename = _mapping_value(merged, "filename") or _mapping_value(behavior_hints, "filename")
    size = _first_present(
        _mapping_value(merged, "size", "videoSize"),
        _mapping_value(behavior_hints, "videoSize"),
    )
    video_hash = _first_present(
        _mapping_value(merged, "videoHash", "video_hash"),
        _mapping_value(behavior_hints, "videoHash"),
    )
    sources = _string_list(_mapping_value(merged, "sources"))
    trackers = _string_list(_mapping_value(merged, "trackers"))
    archive_urls = []
    for key in ("rarUrls", "zipUrls", "sevenZipUrls", "tgzUrls", "tarUrls"):
        archive_urls.extend(_string_list(_mapping_value(merged, key)))

    known_fields = {
        "url", "ytId", "yt_id", "infoHash", "info_hash", "fileIdx", "file_idx",
        "externalUrl", "external_url", "title", "name", "description", "filename", "size",
        "videoSize", "videoHash", "video_hash", "subtitles", "streamSubtitles",
        "stream_subtitles", "sources", "trackers", "proxyHeaders", "proxy_headers", "headers",
        "stremioMetadata", "stremio_metadata", "behaviorHints", "behavior_hints",
        "fileMustInclude", "nzbUrl", "rarUrls", "zipUrls", "sevenZipUrls", "tgzUrls", "tarUrls",
    }
    extra_metadata = dict(metadata) if isinstance(metadata, Mapping) else {}
    extra_metadata.update({key: value for key, value in values.items() if key not in known_fields})

    return StremioPlaybackCandidate(
        url=_string_or_none(_mapping_value(merged, "url")),
        ytId=_string_or_none(_mapping_value(merged, "ytId", "yt_id")),
        infoHash=_string_or_none(_mapping_value(merged, "infoHash", "info_hash")),
        fileIdx=_mapping_value(merged, "fileIdx", "file_idx"),
        externalUrl=_string_or_none(_mapping_value(merged, "externalUrl", "external_url")),
        title=_string_or_none(_mapping_value(merged, "title")),
        name=_string_or_none(_mapping_value(merged, "name")),
        description=_string_or_none(_mapping_value(merged, "description")),
        filename=_string_or_none(filename),
        size=size,
        videoHash=_string_or_none(video_hash),
        subtitles=subtitles,
        sources=sources,
        trackers=trackers,
        headers=request_headers,
        responseHeaders=response_headers,
        fileMustInclude=_string_list_or_none(_mapping_value(merged, "fileMustInclude")),
        nzbUrl=_string_or_none(_mapping_value(merged, "nzbUrl")),
        archiveUrls=archive_urls,
        metadata=extra_metadata,
        origin=origin or _string_or_none(_mapping_value(merged, "origin")) or "",
    )


def candidate_from_payload(data: Any) -> StremioPlaybackCandidate:
    """Create a candidate from a current or legacy action/cache payload."""
    return normalize_stream(data, origin="payload")


def payload_from_torrent(
    source: Any, context: Optional[Mapping[str, Any]] = None
) -> Dict[str, Any]:
    """Convert a current or legacy ``TorrentStream`` into a canonical payload."""
    values = _as_mapping(source)
    metadata = _mapping_value(values, "stremioMetadata", "stremio_metadata")
    metadata = dict(metadata) if isinstance(metadata, Mapping) else {}

    def value(*keys: str, default: Any = None) -> Any:
        result = _mapping_value(metadata, *keys)
        if result is not None:
            return result
        result = _mapping_value(values, *keys)
        return default if result is None else result

    payload = {
        "type": value("type", default=""),
        "debrid_type": value("debridType", "debrid_type", default=""),
        "indexer": value("indexer", default=""),
        "url": value("url", default=""),
        "magnet": value("magnet", default=""),
        "info_hash": value("infoHash", "info_hash", default=""),
        "file_idx": value("fileIdx", "file_idx"),
        "title": value("title", default=""),
        "size": value("size", default=0),
        "filename": value("filename"),
        "is_pack": value("isPack", "is_pack", default=False),
        "stream_subtitles": value(
            "streamSubtitles", "stream_subtitles", "subtitles", default=[]
        ),
        "subtitles": value("subtitles", "streamSubtitles", "stream_subtitles", default=[]),
        "sources": value("sources", default=[]),
        "trackers": value("trackers", default=[]),
        "stremio_metadata": metadata,
    }
    for key in ("ytId", "externalUrl", "videoHash", "fileMustInclude", "nzbUrl"):
        item = value(key)
        if item is not None:
            payload[key] = item

    candidate = candidate_from_payload(payload)
    result = _payload_from_candidate(candidate)
    result.update({key: value for key, value in payload.items() if key not in result})
    if context:
        result["context"] = dict(context)
    return result


def classify(
    candidate: Any, capabilities: Optional[Mapping[str, Any]] = None
) -> Decision:
    """Classify a candidate and reject unsafe capability combinations early."""
    candidate = normalize_stream(candidate)
    capabilities = capabilities or {}

    if _client_is_unsupported(capabilities):
        return _unsupported("unsupported_client", "The selected playback client is unavailable.")
    metadata_problem = _metadata_problem(candidate)
    if metadata_problem:
        return _unsupported(*metadata_problem)
    header_problem = _header_problem(candidate)
    if header_problem:
        return _unsupported(*header_problem)
    if candidate.ytId:
        if _CONTROL_RE.search(candidate.ytId) or "|" in candidate.ytId:
            return _unsupported("malformed_locator", "The video source is malformed.")
        return Decision("youtube", True, "", "youtube")

    archive_present = bool(candidate.nzbUrl or candidate.archiveUrls)
    if archive_present:
        return _unsupported("unsupported_archive", "Archive and Usenet sources are not supported.")
    if candidate.externalUrl and not candidate.url and not candidate.infoHash:
        return _unsupported("external_source", "External web pages are not playable sources.")

    if candidate.url and candidate.url.lower().startswith("magnet:"):
        info_hash, magnet_trackers, magnet_error = _magnet_parts(candidate.url)
        if magnet_error:
            return _unsupported(*magnet_error)
        if candidate.infoHash and candidate.infoHash.lower() != info_hash:
            return _unsupported("malformed_locator", "The torrent locator is malformed.")
        trackers, tracker_error = _normalized_trackers(
            list(candidate.sources) + list(candidate.trackers) + magnet_trackers
        )
        if tracker_error:
            return _unsupported(*tracker_error)
        if not trackers:
            return _unsupported("dht_only", "DHT-only torrent sources are not supported.")
        return _torrent_decision(candidate, capabilities)

    if candidate.url:
        if _valid_http_url(candidate.url):
            if "|" in candidate.url:
                return _unsupported("unsafe_locator", "The direct source locator is unsafe.")
            return Decision("direct_http", True, "", "direct_http")
        return _unsupported("malformed_locator", "The direct source locator is malformed.")

    if candidate.infoHash:
        if not _HASH_RE.fullmatch(candidate.infoHash):
            return _unsupported("malformed_locator", "The torrent hash is malformed.")
        trackers, tracker_error = _normalized_trackers(
            list(candidate.sources) + list(candidate.trackers)
        )
        if tracker_error:
            return _unsupported(*tracker_error)
        if not trackers:
            return _unsupported("dht_only", "DHT-only torrent sources are not supported.")
        return _torrent_decision(candidate, capabilities)

    return _unsupported("unsupported_source", "The source cannot be played by Kodi.")


def resolve(
    candidate: Any,
    context: Optional[Mapping[str, Any]] = None,
    legacy_resolver: Optional[Callable[..., Any]] = None,
) -> Dict[str, Any]:
    """Resolve a classified candidate into a safe canonical playback payload."""
    candidate = normalize_stream(candidate)
    context = context or {}
    decision = classify(candidate, context)
    if not decision.supported:
        raise StremioPlaybackError(decision.code, decision.reason)

    if decision.source_class == "youtube":
        if not _youtube_available(context):
            raise StremioPlaybackError(
                "youtube_addon_unavailable", "The YouTube playback addon is unavailable."
            )
        resolved = _payload_from_candidate(candidate)
        resolved["url"] = (
            f"plugin://{_YOUTUBE_ADDON_ID}/play/?video_id={quote(candidate.ytId or '', safe='')}"
        )
        return resolved

    if decision.source_class == "direct_http":
        resolved = _payload_from_candidate(candidate)
        resolved["url"] = _direct_url_with_headers(candidate)
        return resolved

    magnet = _normalized_magnet(candidate)
    resolved = _payload_from_candidate(candidate)
    resolved["url"] = magnet
    resolved["magnet"] = magnet
    if legacy_resolver:
        try:
            legacy_result = legacy_resolver(dict(resolved), context)
        except TypeError:
            legacy_result = legacy_resolver(dict(resolved))
        if legacy_result is None:
            raise StremioPlaybackError(
                "resolver_failed", "The torrent source could not be resolved."
            )
        if isinstance(legacy_result, str):
            if not legacy_result:
                raise StremioPlaybackError(
                    "resolver_failed", "The torrent source could not be resolved."
                )
            resolved["url"] = legacy_result
        elif isinstance(legacy_result, Mapping):
            resolved.update(legacy_result)
    return resolved


def _as_mapping(value: Any) -> Dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if value is None:
        return {}
    try:
        return dict(vars(value))
    except TypeError:
        return {}


def _mapping_value(values: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in values:
            return values[key]
    return None


def _first_present(*values: Any) -> Any:
    return next((value for value in values if value is not None), None)


def _string_or_none(value: Any) -> Optional[str]:
    return None if value is None else value if isinstance(value, str) else str(value)


def _string_list(value: Any) -> List[str]:
    if value is None or isinstance(value, (str, bytes)):
        return [value] if isinstance(value, str) else []
    return [item for item in value if isinstance(item, str)] if isinstance(value, Iterable) else []


def _string_list_or_none(value: Any) -> Optional[List[str]]:
    return None if value is None else _string_list(value)


def _normalize_subtitles(value: Any) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for subtitle in value or []:
        if isinstance(subtitle, Mapping):
            result.append(dict(subtitle))
        else:
            result.append({
                key: getattr(subtitle, key)
                for key in ("id", "url", "lang")
                if getattr(subtitle, key, None) is not None
            })
    return result


def _split_headers(value: Any) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    if not isinstance(value, Mapping):
        return {}, {}
    if "request" in value or "response" in value:
        request = value.get("request") or {}
        response = value.get("response") or {}
        return _header_mapping(request), _header_mapping(response)
    return dict(value), {}


def _header_mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {"__invalid__": value}


def _metadata_problem(candidate: StremioPlaybackCandidate) -> Optional[Tuple[str, str]]:
    for value in (candidate.filename, candidate.title, candidate.name):
        if value and _DISPLAY_METADATA_CONTROL_RE.search(value):
            return "unsafe_metadata", "The stream metadata contains unsafe characters."
    for subtitle in candidate.subtitles:
        for value in subtitle.values():
            if not isinstance(value, str):
                continue
            if _CONTROL_RE.search(value) or "|" in value:
                return "unsafe_subtitles", "The embedded subtitles contain unsafe characters."
        subtitle_url = subtitle.get("url")
        if subtitle_url and not _valid_http_url(subtitle_url):
            return "malformed_subtitle", "An embedded subtitle source is malformed."
    return None


def _header_problem(candidate: StremioPlaybackCandidate) -> Optional[Tuple[str, str]]:
    if candidate.responseHeaders:
        return (
            "response_headers_unsupported",
            "Response headers require a playback proxy and are not supported here.",
        )
    for name, value in candidate.headers.items():
        if not isinstance(name, str) or not isinstance(value, str):
            return "unsafe_headers", "The source request headers are malformed."
        if not _HEADER_NAME_RE.fullmatch(name) or _CONTROL_RE.search(value):
            return "unsafe_headers", "The source request headers are unsafe."
        if "|" in name or "|" in value or "&" in name:
            return "unsafe_headers", "The source request headers are unsafe."
    return None


def _valid_http_url(value: str) -> bool:
    if not value or _CONTROL_RE.search(value):
        return False
    parsed = urlparse(value)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return False
    return parsed.username is None and parsed.password is None


def _client_is_unsupported(capabilities: Mapping[str, Any]) -> bool:
    if capabilities.get("supported") is False or capabilities.get("client_supported") is False:
        return True
    client = str(capabilities.get("client", "")).lower()
    return client in {"unsupported", "unavailable", "none"}


def _file_index_supported(capabilities: Mapping[str, Any]) -> bool:
    if capabilities.get("supports_file_idx") is True:
        return True
    if capabilities.get("file_index_support") is True:
        return True
    client = capabilities.get("client")
    client_capabilities = capabilities.get("client_capabilities")
    if isinstance(client_capabilities, Mapping) and isinstance(client, str):
        selected = client_capabilities.get(client)
        return isinstance(selected, Mapping) and selected.get("supports_file_idx") is True
    return False


def _torrent_decision(
    candidate: StremioPlaybackCandidate, capabilities: Mapping[str, Any]
) -> Decision:
    if candidate.fileIdx is not None and not _file_index_supported(capabilities):
        return _unsupported(
            "file_index_unsupported",
            "This torrent client cannot verify the requested file index.",
        )
    return Decision("torrent_hash", True, "", "torrent_hash")


def _magnet_parts(value: str) -> Tuple[str, List[str], Optional[Tuple[str, str]]]:
    if _CONTROL_RE.search(value):
        return "", [], ("malformed_locator", "The torrent locator is malformed.")
    parsed = urlparse(value)
    query = parse_qs(parsed.query, keep_blank_values=True)
    xt_values = query.get("xt", [])
    hashes = [unquote(item).split("urn:btih:", 1)[-1] for item in xt_values]
    if not hashes or not _HASH_RE.fullmatch(hashes[0]):
        return "", [], ("malformed_locator", "The torrent locator is malformed.")
    return hashes[0].lower(), query.get("tr", []), None


def _normalized_trackers(values: List[str]) -> Tuple[List[str], Optional[Tuple[str, str]]]:
    normalized = set()
    for value in values:
        if not isinstance(value, str) or _CONTROL_RE.search(value):
            return [], ("unsafe_locator", "The torrent tracker data is unsafe.")
        value = value.strip()
        if value.startswith("tracker:"):
            value = value[len("tracker:") :]
        if value.startswith("dht:") or not value:
            continue
        parsed = urlparse(value)
        if parsed.scheme.lower() not in {"http", "https", "udp", "ws", "wss"} or not parsed.netloc:
            return [], ("malformed_tracker", "The torrent tracker data is malformed.")
        if parsed.username is not None or parsed.password is not None or "|" in value:
            return [], ("unsafe_locator", "The torrent tracker data is unsafe.")
        normalized.add(value)
    return sorted(normalized), None


def _normalized_magnet(candidate: StremioPlaybackCandidate) -> str:
    info_hash = candidate.infoHash or ""
    magnet_trackers = []
    if candidate.url and candidate.url.lower().startswith("magnet:"):
        info_hash, magnet_trackers, _ = _magnet_parts(candidate.url)
    trackers, _ = _normalized_trackers(
        list(candidate.sources) + list(candidate.trackers) + magnet_trackers
    )
    return "magnet:?xt=urn:btih:" + info_hash.lower() + "".join(
        f"&tr={quote(tracker, safe='')}" for tracker in trackers
    )


def _direct_url_with_headers(candidate: StremioPlaybackCandidate) -> str:
    if not candidate.url:
        raise StremioPlaybackError("unsupported_source", "The source cannot be played by Kodi.")
    if not candidate.headers:
        return candidate.url
    values = []
    for name in sorted(candidate.headers, key=str.casefold):
        values.append(f"{name}={quote(candidate.headers[name], safe='')}")
    return candidate.url + "|" + "&".join(values)


def _payload_from_candidate(candidate: StremioPlaybackCandidate) -> Dict[str, Any]:
    return {
        "url": candidate.url or "",
        "title": candidate.title or candidate.name or "",
        "filename": candidate.filename,
        "size": candidate.size,
        "info_hash": candidate.infoHash or "",
        "file_idx": candidate.fileIdx,
        "stream_subtitles": list(candidate.subtitles),
        "subtitles": list(candidate.subtitles),
        "sources": list(candidate.sources),
        "trackers": list(candidate.trackers),
        "headers": dict(candidate.headers),
        "ytId": candidate.ytId,
        "externalUrl": candidate.externalUrl,
        "stremio_metadata": dict(candidate.metadata),
    }


def _youtube_available(context: Mapping[str, Any]) -> bool:
    available = context.get("youtube_available")
    if isinstance(available, bool):
        return available
    for key in ("is_addon_available", "addon_available"):
        checker = context.get(key)
        if callable(checker):
            return bool(checker(_YOUTUBE_ADDON_ID))
    addons = context.get("available_addons")
    return isinstance(addons, (set, list, tuple)) and _YOUTUBE_ADDON_ID in addons


def _unsupported(code: str, reason: str) -> Decision:
    return Decision("unsupported", False, reason, code)


def _safe_message(message: str) -> str:
    message = _CONTROL_RE.sub(" ", str(message))
    message = re.sub(r"https?://[^\s/@]+@", "https://<redacted>@", message, flags=re.IGNORECASE)
    message = re.sub(
        r"(?i)\b(authorization|cookie|token|password|secret)\b[^\s,;]*",
        r"\1=<redacted>",
        message,
    )
    return message
