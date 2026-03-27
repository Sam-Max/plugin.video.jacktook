import re
import time
from typing import Dict, List, Optional
from urllib.parse import parse_qs, urlparse

import requests

from lib.clients.tmdb.trailers import resolve_tmdb_trailer
from lib.utils.kodi.utils import kodilog


WATCH_URL = "https://www.youtube.com/watch"
PLAYER_URL = "https://www.youtube.com/youtubei/v1/player"
CACHE_TTL_SECONDS = 300
VIDEO_CONTAINER_NEAR_TIE_BITRATE_MARGIN = 250000
VIDEO_CONTAINER_NEAR_TIE_RATIO = 0.10
WATCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
YOUTUBE_CLIENTS = [
    {
        "key": "android_vr",
        "clientName": "ANDROID_VR",
        "clientVersion": "1.56.21",
        "client_id": "28",
        "user_agent": (
            "com.google.android.apps.youtube.vr.oculus/1.56.21 "
            "(Linux; U; Android 12; en_US; Quest 3; Build/SQ3A.220605.009.A1) gzip"
        ),
        "context": {
            "clientName": "ANDROID_VR",
            "clientVersion": "1.56.21",
            "deviceMake": "Oculus",
            "deviceModel": "Quest 3",
            "osName": "Android",
            "osVersion": "12",
            "platform": "MOBILE",
            "androidSdkVersion": 32,
            "hl": "en",
            "gl": "US",
        },
    },
    {
        "key": "android",
        "clientName": "ANDROID",
        "clientVersion": "20.10.35",
        "client_id": "3",
        "user_agent": "com.google.android.youtube/20.10.35 (Linux; U; Android 14; en_US) gzip",
        "context": {
            "clientName": "ANDROID",
            "clientVersion": "20.10.35",
            "osName": "Android",
            "osVersion": "14",
            "platform": "MOBILE",
            "androidSdkVersion": 34,
            "hl": "en",
            "gl": "US",
        },
    },
    {
        "key": "ios",
        "clientName": "IOS",
        "clientVersion": "20.10.1",
        "client_id": "5",
        "user_agent": "com.google.ios.youtube/20.10.1 (iPhone16,2; U; CPU iOS 17_4 like Mac OS X)",
        "context": {
            "clientName": "IOS",
            "clientVersion": "20.10.1",
            "deviceModel": "iPhone16,2",
            "osName": "iPhone",
            "osVersion": "17.4.0.21E219",
            "platform": "MOBILE",
            "hl": "en",
            "gl": "US",
        },
    },
]
_VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
_RESOLVER_CACHE = {}


def extract_video_id(value: Optional[str]) -> Optional[str]:
    if not value:
        return None

    candidate = value.strip()
    if _VIDEO_ID_PATTERN.match(candidate):
        return candidate

    try:
        parsed = urlparse(candidate)
    except Exception:
        return None

    host = (parsed.netloc or "").lower()
    path_parts = [part for part in parsed.path.split("/") if part]

    if host in ("youtu.be", "www.youtu.be") and path_parts:
        return path_parts[0] if _VIDEO_ID_PATTERN.match(path_parts[0]) else None

    if host.endswith("youtube.com") or host.endswith("youtube-nocookie.com"):
        query_video_id = parse_qs(parsed.query).get("v", [None])[0]
        if query_video_id and _VIDEO_ID_PATTERN.match(query_video_id):
            return query_video_id

        if len(path_parts) >= 2 and path_parts[0] in ("embed", "shorts", "live"):
            return path_parts[1] if _VIDEO_ID_PATTERN.match(path_parts[1]) else None

    return None


def parse_watch_config(html: str) -> Optional[Dict[str, Optional[str]]]:
    if not html:
        return None

    api_key_match = re.search(r'"INNERTUBE_API_KEY"\s*:\s*"([^"]+)"', html)
    if not api_key_match:
        return None

    visitor_match = re.search(r'"VISITOR_DATA"\s*:\s*"([^"]+)"', html)
    return {
        "api_key": api_key_match.group(1),
        "visitor_data": visitor_match.group(1) if visitor_match else None,
    }


def _video_score(fmt: Dict[str, object]):
    return (
        int(fmt.get("height") or 0),
        int(fmt.get("fps") or 0),
        int(fmt.get("bitrate") or fmt.get("averageBitrate") or 0),
    )


def _audio_score(fmt: Dict[str, object]):
    sample_rate = fmt.get("audioSampleRate") or 0
    try:
        sample_rate = int(sample_rate)
    except (TypeError, ValueError):
        sample_rate = 0

    return (
        int(fmt.get("bitrate") or fmt.get("averageBitrate") or 0),
        sample_rate,
    )


def _container_rank(mime_type: object) -> int:
    mime_type = str(mime_type or "").lower()
    if "mp4" in mime_type or "m4a" in mime_type:
        return 0
    if "webm" in mime_type:
        return 1
    return 2


def _video_rank(fmt: Dict[str, object]):
    height, fps, bitrate = _video_score(fmt)
    return (height, fps, -_container_rank(fmt.get("mimeType")), bitrate)


def _audio_rank(fmt: Dict[str, object]):
    bitrate, sample_rate = _audio_score(fmt)
    return (bitrate, sample_rate, -_container_rank(fmt.get("mimeType")))


def _video_bitrate_near_tie(left_bitrate: int, right_bitrate: int) -> bool:
    margin = max(
        VIDEO_CONTAINER_NEAR_TIE_BITRATE_MARGIN,
        int(max(left_bitrate, right_bitrate) * VIDEO_CONTAINER_NEAR_TIE_RATIO),
    )
    return abs(left_bitrate - right_bitrate) <= margin


def _choose_better_video_format(best_fmt: Dict[str, object], candidate_fmt: Dict[str, object]):
    best_height, best_fps, best_bitrate = _video_score(best_fmt)
    candidate_height, candidate_fps, candidate_bitrate = _video_score(candidate_fmt)

    if candidate_height != best_height:
        return candidate_fmt if candidate_height > best_height else best_fmt

    if candidate_fps != best_fps:
        return candidate_fmt if candidate_fps > best_fps else best_fmt

    best_container_rank = _container_rank(best_fmt.get("mimeType"))
    candidate_container_rank = _container_rank(candidate_fmt.get("mimeType"))
    if (
        candidate_container_rank != best_container_rank
        and _video_bitrate_near_tie(candidate_bitrate, best_bitrate)
    ):
        return candidate_fmt if candidate_container_rank < best_container_rank else best_fmt

    if candidate_bitrate != best_bitrate:
        return candidate_fmt if candidate_bitrate > best_bitrate else best_fmt

    if candidate_container_rank != best_container_rank:
        return candidate_fmt if candidate_container_rank < best_container_rank else best_fmt

    return candidate_fmt if _video_rank(candidate_fmt) > _video_rank(best_fmt) else best_fmt


def _select_best_video_format(formats: List[Dict[str, object]]) -> Optional[Dict[str, object]]:
    if not formats:
        return None

    best_format = formats[0]
    for fmt in formats[1:]:
        best_format = _choose_better_video_format(best_format, fmt)

    return best_format


def select_best_stream(player_response: Dict) -> Optional[Dict[str, Optional[str]]]:
    streaming_data = player_response.get("streamingData") or {}
    hls_manifest_url = streaming_data.get("hlsManifestUrl")

    progressive_formats = []
    for fmt in streaming_data.get("formats") or []:
        mime_type = str(fmt.get("mimeType") or "")
        url = fmt.get("url")
        if not url or "video/" not in mime_type:
            continue
        progressive_formats.append(fmt)

    adaptive_video_formats = []
    adaptive_audio_formats = []
    for fmt in streaming_data.get("adaptiveFormats") or []:
        mime_type = str(fmt.get("mimeType") or "")
        url = fmt.get("url")
        if not url:
            continue
        if "video/" in mime_type:
            adaptive_video_formats.append(fmt)
        elif "audio/" in mime_type:
            adaptive_audio_formats.append(fmt)

    if adaptive_video_formats and adaptive_audio_formats:
        best_video = _select_best_video_format(adaptive_video_formats)
        best_audio = max(adaptive_audio_formats, key=_audio_rank)
        return {
            "video_url": best_video.get("url"),
            "audio_url": best_audio.get("url"),
            "source_type": "adaptive",
        }

    if progressive_formats:
        best_format = _select_best_video_format(progressive_formats)
        return {
            "video_url": best_format.get("url"),
            "audio_url": None,
            "source_type": "progressive",
        }

    if hls_manifest_url:
        return {
            "video_url": hls_manifest_url,
            "audio_url": None,
            "source_type": "hls",
        }

    return None


def resolve_trailer_playback(
    video_id: Optional[str] = None,
    youtube_url: Optional[str] = None,
    session: Optional[requests.Session] = None,
    cache_ttl: int = CACHE_TTL_SECONDS,
) -> Optional[Dict[str, Optional[str]]]:
    normalized_video_id = extract_video_id(video_id or youtube_url)
    if not normalized_video_id:
        kodilog(
            f"Trailer/YouTube: invalid video id input video_id={video_id!r} youtube_url={youtube_url!r}"
        )
        return None

    cached = _get_cached_result(normalized_video_id)
    if cached:
        return cached

    http_session = session or requests.Session()

    try:
        watch_response = http_session.get(
            WATCH_URL,
            params={"v": normalized_video_id},
            headers=WATCH_HEADERS.copy(),
            timeout=10,
        )
        watch_response.raise_for_status()
    except Exception as exc:
        kodilog(
            f"Trailer/YouTube: watch request failed video_id={normalized_video_id!r} error={exc}"
        )
        return None

    watch_config = parse_watch_config(watch_response.text)
    if not watch_config:
        kodilog(
            f"Trailer/YouTube: missing watch config video_id={normalized_video_id!r}"
        )
        return None

    for client in YOUTUBE_CLIENTS:
        payload = _call_player_api(
            http_session=http_session,
            client=client,
            watch_config=watch_config,
            normalized_video_id=normalized_video_id,
        )
        if payload and payload.get("_request_failed"):
            kodilog(
                "Trailer/YouTube: player api failed "
                f"video_id={normalized_video_id!r} client={client['clientName']!r} "
                f"status_code={payload.get('_status_code')!r} error={payload.get('_error')!r} "
                f"preview={payload.get('_preview')!r}"
            )
            continue

        if not payload:
            kodilog(
                f"Trailer/YouTube: player api failed video_id={normalized_video_id!r} client={client['clientName']!r}"
            )
            continue

        if not _is_playable(payload):
            status = ((payload.get("playabilityStatus") or {}).get("status") or "").upper()
            kodilog(
                f"Trailer/YouTube: unplayable response video_id={normalized_video_id!r} client={client['clientName']!r} status={status!r}"
            )
            continue

        stream = select_best_stream(payload)
        if not stream:
            kodilog(
                f"Trailer/YouTube: no playable stream video_id={normalized_video_id!r} client={client['clientName']!r}"
            )
            continue

        result = dict(stream)
        result["video_id"] = normalized_video_id
        _set_cached_result(normalized_video_id, result, cache_ttl)
        kodilog(
            f"Trailer/YouTube: resolved video_id={normalized_video_id!r} client={client['clientName']!r} source_type={result.get('source_type')!r}"
        )
        return result

    kodilog(f"Trailer/YouTube: exhausted clients without stream video_id={normalized_video_id!r}")
    return None


def resolve_item_trailer_playback(
    item=None,
    yt_id: Optional[str] = None,
    youtube_url: Optional[str] = None,
    tmdb_id: Optional[object] = None,
    media_type: Optional[str] = None,
    session: Optional[requests.Session] = None,
    cache_ttl: int = CACHE_TTL_SECONDS,
) -> Optional[Dict[str, Optional[str]]]:
    result = resolve_item_trailer(
        item=item,
        yt_id=yt_id,
        youtube_url=youtube_url,
        tmdb_id=tmdb_id,
        media_type=media_type,
        session=session,
        cache_ttl=cache_ttl,
    )

    return result.get("playback") if result else None


def resolve_item_trailer(
    item=None,
    yt_id: Optional[str] = None,
    youtube_url: Optional[str] = None,
    tmdb_id: Optional[object] = None,
    media_type: Optional[str] = None,
    session: Optional[requests.Session] = None,
    cache_ttl: int = CACHE_TTL_SECONDS,
) -> Optional[Dict[str, Optional[Dict[str, Optional[str]]]]]:
    trailer = resolve_item_trailer_metadata(
        item=item,
        yt_id=yt_id,
        youtube_url=youtube_url,
        tmdb_id=tmdb_id,
        media_type=media_type,
    )

    if not trailer:
        return None

    playback = resolve_trailer_playback(
        video_id=trailer.get("yt_id"),
        youtube_url=trailer.get("youtube_url"),
        session=session,
        cache_ttl=cache_ttl,
    )

    return {
        "trailer": trailer,
        "playback": playback,
    }


def resolve_item_trailer_metadata(
    item=None,
    yt_id: Optional[str] = None,
    youtube_url: Optional[str] = None,
    tmdb_id: Optional[object] = None,
    media_type: Optional[str] = None,
) -> Optional[Dict[str, Optional[str]]]:
    direct_video_id = yt_id or _get_item_value(item, "yt_id", "ytId")
    direct_youtube_url = youtube_url or _get_item_value(item, "youtube_url", "youtubeUrl")
    resolved_tmdb_id = tmdb_id or _get_item_value(item, "tmdb_id", "id")
    resolved_media_type = media_type or _get_item_value(item, "media_type", "type")

    trailer = None
    if direct_video_id or direct_youtube_url:
        kodilog(
            f"Trailer: using direct youtube metadata tmdb_id={resolved_tmdb_id!r} media_type={resolved_media_type!r} yt_id={direct_video_id!r} youtube_url={direct_youtube_url!r}"
        )
        trailer = {
            "yt_id": direct_video_id,
            "youtube_url": direct_youtube_url,
        }
    else:
        kodilog(
            f"Trailer: requesting TMDB trailer tmdb_id={resolved_tmdb_id!r} media_type={resolved_media_type!r}"
        )
        trailer = resolve_tmdb_trailer(resolved_tmdb_id, resolved_media_type)

    if not trailer:
        kodilog(
            f"Trailer: no trailer metadata available tmdb_id={resolved_tmdb_id!r} media_type={resolved_media_type!r}"
        )
        return None

    return trailer


def _call_player_api(
    http_session: requests.Session,
    client: Dict[str, object],
    watch_config: Dict[str, Optional[str]],
    normalized_video_id: str,
) -> Optional[Dict]:
    headers = WATCH_HEADERS.copy()
    headers.update(
        {
            "Content-Type": "application/json",
            "Origin": "https://www.youtube.com",
            "User-Agent": str(client["user_agent"]),
            "X-YouTube-Client-Name": str(client["client_id"]),
            "X-YouTube-Client-Version": str(client["clientVersion"]),
        }
    )
    if watch_config.get("visitor_data"):
        headers["X-Goog-Visitor-Id"] = str(watch_config["visitor_data"])

    try:
        response = http_session.post(
            PLAYER_URL,
            params={"key": watch_config["api_key"]},
            headers=headers,
            json={
                "videoId": normalized_video_id,
                "contentCheckOk": True,
                "racyCheckOk": True,
                "context": {"client": dict(client["context"])},
                "playbackContext": {
                    "contentPlaybackContext": {
                        "html5Preference": "HTML5_PREF_WANTS",
                    }
                },
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        preview = ""
        status_code = None
        if "response" in locals():
            preview = getattr(response, "text", "")[:200]
            status_code = getattr(response, "status_code", None)
        return {
            "_request_failed": True,
            "_error": str(exc),
            "_preview": preview,
            "_status_code": status_code,
        }


def _is_playable(player_response: Dict) -> bool:
    status = ((player_response.get("playabilityStatus") or {}).get("status") or "").upper()
    return status == "OK"


def _get_item_value(item, *keys):
    if item is None:
        return None

    for key in keys:
        if isinstance(item, dict) and key in item:
            return item.get(key)
        if hasattr(item, key):
            return getattr(item, key)

    return None


def _get_cached_result(video_id: str) -> Optional[Dict[str, Optional[str]]]:
    cached = _RESOLVER_CACHE.get(video_id)
    if not cached:
        return None

    if cached["expires_at"] <= time.time():
        _RESOLVER_CACHE.pop(video_id, None)
        return None

    return dict(cached["value"])


def _set_cached_result(video_id: str, value: Dict[str, Optional[str]], ttl: int) -> None:
    _RESOLVER_CACHE[video_id] = {
        "expires_at": time.time() + max(ttl, 0),
        "value": dict(value),
    }
