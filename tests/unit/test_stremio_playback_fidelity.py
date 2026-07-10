import pytest

from lib.api.stremio.models import Stream
from lib.clients.stremio.playback import (
    StremioPlaybackError,
    candidate_from_payload,
    classify,
    normalize_stream,
    payload_from_torrent,
    resolve,
)
from lib.domain.torrent import TorrentStream

INFO_HASH = "0123456789abcdef0123456789abcdef01234567"
TRACKER_A = "https://tracker-a.example/announce"
TRACKER_B = "https://tracker-b.example/announce"


def _supported_hash_payload(**overrides):
    payload = {
        "infoHash": INFO_HASH,
        "sources": [TRACKER_B],
        "trackers": [TRACKER_A],
        "title": "Movie 1080p",
    }
    payload.update(overrides)
    return payload


def test_normalize_stream_preserves_source_metadata_and_subtitles():
    stream = Stream.from_dict(
        {
            "url": "https://media.example/movie.mkv",
            "infoHash": INFO_HASH,
            "fileIdx": 2,
            "title": "Movie 1080p",
            "sources": [TRACKER_B],
            "trackers": [TRACKER_A],
            "subtitles": [{"id": "sub-en", "url": "https://sub.example/en.vtt", "lang": "eng"}],
            "behaviorHints": {
                "filename": "Movie.1080p.mkv",
                "videoSize": 123456,
                "videoHash": "video-hash",
                "proxyHeaders": {"request": {"Referer": "https://media.example"}},
            },
        }
    )

    candidate = normalize_stream(stream, origin="search")

    assert candidate.url == "https://media.example/movie.mkv"
    assert candidate.infoHash == INFO_HASH
    assert candidate.fileIdx == 2
    assert candidate.filename == "Movie.1080p.mkv"
    assert candidate.size == 123456
    assert candidate.videoHash == "video-hash"
    assert candidate.sources == [TRACKER_B]
    assert candidate.trackers == [TRACKER_A]
    assert candidate.subtitles == [
        {"id": "sub-en", "url": "https://sub.example/en.vtt", "lang": "eng"}
    ]
    assert candidate.origin == "search"


def test_normalize_stream_accepts_payloads_and_uses_safe_optional_defaults():
    candidate = normalize_stream({"title": "Legacy stream"}, origin="cache")

    assert candidate.title == "Legacy stream"
    assert candidate.url is None
    assert candidate.infoHash is None
    assert candidate.fileIdx is None
    assert candidate.sources == []
    assert candidate.trackers == []
    assert candidate.subtitles == []
    assert candidate.headers == {}


def test_legacy_torrent_cache_and_payload_round_trip_keep_available_metadata():
    source = TorrentStream(
        title="Cached movie",
        url="https://media.example/movie.mkv",
        infoHash=INFO_HASH,
        size=9876,
        streamSubtitles=[{"url": "https://sub.example/movie.vtt", "lang": "eng"}],
    )

    payload = payload_from_torrent(source)
    candidate = candidate_from_payload(payload)

    assert payload["stream_subtitles"] == source.streamSubtitles
    assert candidate.title == "Cached movie"
    assert candidate.url == source.url
    assert candidate.infoHash == INFO_HASH
    assert candidate.size == 9876
    assert candidate.subtitles == source.streamSubtitles
    assert candidate.sources == []
    assert candidate.trackers == []

    legacy_payload = payload_from_torrent(
        {
            "title": "Older cached movie",
            "url": source.url,
            "infoHash": INFO_HASH,
            "streamSubtitles": source.streamSubtitles,
        }
    )
    assert candidate_from_payload(legacy_payload).title == "Older cached movie"


@pytest.mark.parametrize(
    ("payload", "source_class"),
    [
        ({"url": "https://media.example/movie.mkv"}, "direct_http"),
        (_supported_hash_payload(), "torrent_hash"),
        ({"ytId": "youtube-video-id"}, "youtube"),
    ],
)
def test_classify_supported_source_families(payload, source_class):
    decision = classify(normalize_stream(payload))

    assert decision.source_class == source_class
    assert decision.supported is True


@pytest.mark.parametrize(
    "payload",
    [
        {"externalUrl": "https://external.example/watch"},
        {"rarUrls": ["https://archive.example/movie.rar"]},
        {"zipUrls": ["https://archive.example/movie.zip"]},
        {"nzbUrl": "https://usenet.example/movie.nzb"},
        {"url": "magnet:?xt=urn:btih:" + INFO_HASH},
        {"url": "javascript:alert(1)"},
        {"url": "https://"},
        {},
    ],
)
def test_classify_rejects_unsupported_or_malformed_locators(payload):
    decision = classify(normalize_stream(payload))

    assert decision.source_class == "unsupported"
    assert decision.supported is False
    assert decision.reason


def test_hash_resolution_deterministically_combines_sources_and_legacy_trackers():
    candidate = normalize_stream(
        _supported_hash_payload(
            sources=[TRACKER_B, TRACKER_A],
            trackers=[TRACKER_A, "https://tracker-c.example/announce"],
        )
    )

    resolved = resolve(candidate, {"client": "torrest"})

    assert resolved["url"] == (
        "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567"
        "&tr=https%3A%2F%2Ftracker-a.example%2Fannounce"
        "&tr=https%3A%2F%2Ftracker-b.example%2Fannounce"
        "&tr=https%3A%2F%2Ftracker-c.example%2Fannounce"
    )
    assert resolved["info_hash"] == INFO_HASH


def test_direct_resolution_encodes_valid_request_headers_only():
    candidate = normalize_stream(
        {
            "url": "https://media.example/movie.mkv",
            "behaviorHints": {
                "proxyHeaders": {
                    "request": {
                        "User-Agent": "Jacktook Test",
                        "Referer": "https://media.example/source",
                    }
                }
            },
        }
    )

    resolved = resolve(candidate)

    assert resolved["url"] == (
        "https://media.example/movie.mkv|Referer=https%3A%2F%2Fmedia.example%2Fsource"
        "&User-Agent=Jacktook%20Test"
    )


@pytest.mark.parametrize(
    "headers",
    [
        {"response": {"Content-Type": "video/mkv"}},
        {"request": {"X-Bad": "value|injected"}},
        {"request": {"X-Bad\nName": "value"}},
        {"request": {"X-Bad": 123}},
    ],
)
def test_direct_resolution_rejects_response_only_or_unsafe_headers(headers):
    candidate = normalize_stream(
        {
            "url": "https://media.example/movie.mkv",
            "behaviorHints": {"proxyHeaders": headers},
        }
    )

    with pytest.raises(StremioPlaybackError) as error:
        resolve(candidate)

    assert error.value.code in {"response_headers_unsupported", "unsafe_headers"}
    assert "media.example" not in str(error.value)


def test_errors_redact_locator_credentials_and_sensitive_header_values():
    candidate = normalize_stream(
        {
            "url": "https://user:locator-secret@media.example/movie.mkv",
            "behaviorHints": {
                "proxyHeaders": {"request": {"Authorization": "Bearer header-secret"}}
            },
        }
    )

    with pytest.raises(StremioPlaybackError) as error:
        resolve(candidate)

    message = str(error.value)
    assert "locator-secret" not in message
    assert "header-secret" not in message
    assert "Authorization" not in message


def test_unverified_file_index_is_rejected_before_resolution():
    candidate = normalize_stream(_supported_hash_payload(fileIdx=3))

    decision = classify(candidate, {"client": "torrest"})
    assert decision.source_class == "unsupported"
    assert decision.code == "file_index_unsupported"

    with pytest.raises(StremioPlaybackError) as error:
        resolve(candidate, {"client": "torrest"})
    assert error.value.code == "file_index_unsupported"


def test_verified_file_index_is_preserved_for_a_capable_client():
    candidate = normalize_stream(_supported_hash_payload(fileIdx=3))

    decision = classify(candidate, {"client": "torrest", "supports_file_idx": True})
    resolved = resolve(candidate, {"client": "torrest", "supports_file_idx": True})

    assert decision.source_class == "torrent_hash"
    assert resolved["file_idx"] == 3


def test_unsupported_client_is_rejected_before_a_playable_output_is_created():
    candidate = normalize_stream(_supported_hash_payload())

    with pytest.raises(StremioPlaybackError) as error:
        resolve(candidate, {"client": "unsupported", "supported": False})

    assert error.value.code == "unsupported_client"
    assert "unsupported" not in str(error.value).lower()


def test_youtube_resolution_requires_the_addon_and_returns_an_addon_url():
    candidate = normalize_stream({"ytId": "youtube-video-id", "title": "Trailer"})

    resolved = resolve(candidate, {"youtube_available": True})
    assert resolved["url"] == "plugin://plugin.video.youtube/play/?video_id=youtube-video-id"

    with pytest.raises(StremioPlaybackError) as error:
        resolve(candidate, {"youtube_available": False})
    assert error.value.code == "youtube_addon_unavailable"


def test_empty_url_never_becomes_a_playable_output():
    candidate = normalize_stream({"url": ""})

    with pytest.raises(StremioPlaybackError) as error:
        resolve(candidate)

    assert error.value.code == "unsupported_source"
