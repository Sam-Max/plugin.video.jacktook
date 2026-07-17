import json
from unittest.mock import MagicMock

import pytest

from lib import search
from lib.api.stremio.addon_manager import AddonManager
from lib.api.stremio.models import Meta, MetaBehaviorHints, Stream, Video
from lib.clients.stremio import addon_client, catalog_menus
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


def _stremio_addon_client(monkeypatch):
    addon_manager = AddonManager(
        [
            {
                "manifest": {
                    "id": "org.example.addon",
                    "name": "Example Addon",
                    "resources": [],
                    "types": [],
                },
                "transportUrl": "https://example.com/manifest.json",
                "transportName": "custom",
            }
        ]
    )
    monkeypatch.setattr(addon_client, "get_addon_display_name", lambda addon: addon.manifest.name)
    monkeypatch.setattr(addon_client, "find_languages_in_string", lambda _description: [])
    return addon_client.StremioAddonClient(addon_manager.addons[0])


def _stremio_stream_data(**overrides):
    stream = {
        "url": "https://media.example/movie.mkv",
        "infoHash": INFO_HASH,
        "fileIdx": 2,
        "title": "Movie 1080p",
        "name": "Torrentio Example",
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
    stream.update(overrides)
    return stream


def _stremio_response(data):
    return type("Response", (), {"json": lambda self: data})()


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


@pytest.mark.parametrize("field", ["title", "name", "filename"])
def test_pipe_in_display_metadata_survives_classification_resolution_and_search(
    monkeypatch, field
):
    value = "Release | 1080p"
    payload = {"url": "https://media.example/movie.mkv", field: value}
    candidate = normalize_stream(payload)

    decision = classify(candidate)
    resolved = resolve(candidate)

    assert decision.source_class == "direct_http"
    assert decision.supported is True
    assert resolved["url"] == payload["url"]
    assert getattr(candidate, field) == value

    source = TorrentStream(
        addonKey="org.example.addon|https://example.com",
        url=payload["url"],
        stremioMetadata={field: value},
    )
    notifications = []
    monkeypatch.setattr(search, "_stremio_capabilities", lambda: {})
    monkeypatch.setattr(search, "notification", notifications.append)

    prepared = search._prepare_stremio_results([source])

    assert prepared == [source]
    assert notifications == []
    prepared_candidate = candidate_from_payload(payload_from_torrent(prepared[0]))
    assert getattr(prepared_candidate, field) == value


@pytest.mark.parametrize("separator", ["\n", "\r", "\t"], ids=["lf", "cr", "tab"])
@pytest.mark.parametrize("field", ["title", "name", "filename"])
def test_display_separators_in_display_metadata_are_accepted(field, separator):
    value = f"Release{separator}1080p"
    candidate = normalize_stream(
        {"url": "https://media.example/movie.mkv", field: value}
    )

    decision = classify(candidate)
    resolved = resolve(candidate)

    assert decision.source_class == "direct_http"
    assert decision.supported is True
    assert resolved["url"] == "https://media.example/movie.mkv"
    assert getattr(candidate, field) == value


@pytest.mark.parametrize("control_character", ["\x00", "\x0b", "\x7f"], ids=["nul", "vertical_tab", "del"])
@pytest.mark.parametrize("field", ["title", "name", "filename"])
def test_unsafe_control_characters_in_display_metadata_remain_rejected(
    field, control_character
):
    candidate = normalize_stream(
        {"url": "https://media.example/movie.mkv", field: f"Release{control_character}name"}
    )

    decision = classify(candidate)

    assert decision.source_class == "unsupported"
    assert decision.code == "unsafe_metadata"
    with pytest.raises(StremioPlaybackError) as error:
        resolve(candidate)
    assert error.value.code == "unsafe_metadata"


def test_stremio_rejection_log_redacts_unsafe_metadata(monkeypatch):
    source = TorrentStream(
        addonKey="org.example.addon|https://example.com",
        url="https://media.example/movie.mkv",
        stremioMetadata={"title": "Secret title\x0bTOP-SECRET"},
    )
    logs = []
    notifications = []

    monkeypatch.setattr(search, "_stremio_capabilities", lambda: {})
    monkeypatch.setattr(search, "kodilog", lambda message, *_args: logs.append(message))
    monkeypatch.setattr(search, "notification", notifications.append)

    assert search._prepare_stremio_results([source]) == []
    assert logs == ["stremio_result index=0 decision=unsafe_metadata title=U+000B"]
    assert "TOP-SECRET" not in logs[0]
    assert notifications == ["The stream metadata contains unsafe characters."]


def test_pipe_in_direct_locator_remains_rejected():
    candidate = normalize_stream({"url": "https://media.example/movie.mkv|X-Test=value"})

    decision = classify(candidate)

    assert decision.source_class == "unsupported"
    assert decision.code == "unsafe_locator"
    with pytest.raises(StremioPlaybackError) as error:
        resolve(candidate)
    assert error.value.code == "unsafe_locator"


@pytest.mark.parametrize(
    "payload",
    [
        {"externalUrl": "https://external.example/watch"},
        {"rarUrls": ["https://archive.example/movie.rar"]},
        {"zipUrls": ["https://archive.example/movie.zip"]},
        {"7zipUrls": ["https://archive.example/movie.7z"]},
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


def test_normalize_stream_treats_raw_7zip_urls_as_known_archive_urls():
    archive_url = "https://archive.example/movie.7z"

    candidate = normalize_stream({"7zipUrls": [archive_url]})

    assert candidate.archiveUrls == [archive_url]
    assert "7zipUrls" not in candidate.metadata
    assert classify(candidate).source_class == "unsupported"


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


@pytest.mark.parametrize(
    ("metadata", "expected_is_torrent"),
    [
        (_supported_hash_payload(), True),
        ({"url": "https://media.example/movie.mkv"}, False),
    ],
    ids=["torrent_hash", "direct_http"],
)
def test_stremio_resolution_derives_legacy_torrent_context_from_source_class(
    monkeypatch, metadata, expected_is_torrent
):
    contexts = []
    legacy_contexts = []
    real_resolve = search.resolve

    def resolve_spy(candidate, context=None, legacy_resolver=None):
        contexts.append(dict(context or {}))
        return real_resolve(candidate, context, legacy_resolver=legacy_resolver)

    def legacy_resolver_spy(data):
        legacy_contexts.append(data["is_torrent"])
        return data

    monkeypatch.setattr(search, "resolve", resolve_spy)
    monkeypatch.setattr(search, "resolve_playback_url", legacy_resolver_spy)

    resolved = search._resolve_stremio_source(
        {
            "addonKey": "org.example.addon|https://example.com",
            "stremioMetadata": metadata,
        },
        {"is_torrent": False},
    )

    assert contexts[0]["is_torrent"] is expected_is_torrent
    assert legacy_contexts == ([True] if expected_is_torrent else [])
    if not expected_is_torrent:
        assert resolved["is_torrent"] is False


def test_stremio_unverified_file_index_remains_rejected_before_legacy_resolution(
    monkeypatch,
):
    legacy_calls = []
    source = {
        "addonKey": "org.example.addon|https://example.com",
        "stremioMetadata": _supported_hash_payload(fileIdx=3),
    }

    monkeypatch.setattr(
        search,
        "resolve_playback_url",
        lambda data: legacy_calls.append(data) or data,
    )

    with pytest.raises(StremioPlaybackError) as error:
        search._resolve_stremio_source(source, {"is_torrent": False})

    assert error.value.code == "file_index_unsupported"
    assert legacy_calls == []


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


def test_parse_response_stores_the_normalized_metadata_contract(monkeypatch):
    client = _stremio_addon_client(monkeypatch)

    results = client.parse_response(_stremio_response({"streams": [_stremio_stream_data()]}))

    assert len(results) == 1
    source = results[0]
    payload = payload_from_torrent(source)

    assert payload["url"] == "https://media.example/movie.mkv"
    assert payload["info_hash"] == INFO_HASH
    assert payload["file_idx"] == 2
    assert payload["sources"] == [TRACKER_B]
    assert payload["trackers"] == [TRACKER_A]
    assert payload["headers"] == {"Referer": "https://media.example"}
    assert payload["filename"] == "Movie.1080p.mkv"
    assert payload["size"] == 123456
    assert payload["stream_subtitles"] == [
        {"id": "sub-en", "url": "https://sub.example/en.vtt", "lang": "eng"}
    ]
    assert payload["videoHash"] == "video-hash"


def test_parse_response_keeps_youtube_metadata_and_drops_unsupported_sources(monkeypatch):
    client = _stremio_addon_client(monkeypatch)

    results = client.parse_response(
        _stremio_response(
            {
                "streams": [
                    {
                        "ytId": "youtube-video-id",
                        "title": "Trailer",
                        "subtitles": [
                            {
                                "id": "sub-en",
                                "url": "https://sub.example/trailer.vtt",
                                "lang": "eng",
                            }
                        ],
                    },
                    {"externalUrl": "https://external.example/watch", "title": "External page"},
                ]
            }
        )
    )

    assert len(results) == 1
    payload = payload_from_torrent(results[0])
    assert payload["ytId"] == "youtube-video-id"
    assert payload["stream_subtitles"] == [
        {"id": "sub-en", "url": "https://sub.example/trailer.vtt", "lang": "eng"}
    ]


def test_run_search_entry_preserves_stremio_metadata_for_source_selection(monkeypatch):
    client = _stremio_addon_client(monkeypatch)
    source = client.parse_response(_stremio_response({"streams": [_stremio_stream_data()]}))[0]
    captured = {}

    monkeypatch.setattr(search, "_handle_super_quick_play", lambda _params: False)
    monkeypatch.setattr(search, "set_content_type", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(search, "set_watched_title", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(search, "search_client", lambda *_args, **_kwargs: [source])
    monkeypatch.setattr(search, "_process_search_results", lambda results, *_args, **_kwargs: results)
    monkeypatch.setattr(search, "auto_play_enabled", lambda: False)
    monkeypatch.setattr(
        search,
        "show_source_select",
        lambda results, *_args, **_kwargs: captured.setdefault("results", results) or True,
    )

    search.run_search_entry(
        {
            "query": "Movie",
            "mode": "movies",
            "media_type": "movies",
            "ids": '{"imdb_id": "tt123"}',
        }
    )

    assert payload_from_torrent(captured["results"][0])["stream_subtitles"] == source.streamSubtitles
    assert payload_from_torrent(captured["results"][0])["file_idx"] == 2
    assert payload_from_torrent(captured["results"][0])["headers"] == {
        "Referer": "https://media.example"
    }


def test_run_search_entry_autoplay_resolves_the_canonical_stremio_payload(monkeypatch):
    client = _stremio_addon_client(monkeypatch)
    source = client.parse_response(_stremio_response({"streams": [_stremio_stream_data()]}))[0]
    source.quality = "1080p"
    played = []

    class FakePlayer:
        def run(self, data):
            played.append(data)

    monkeypatch.setattr(search, "_handle_super_quick_play", lambda _params: False)
    monkeypatch.setattr(search, "set_content_type", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(search, "set_watched_title", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(search, "search_client", lambda *_args, **_kwargs: [source])
    monkeypatch.setattr(search, "_process_search_results", lambda results, *_args, **_kwargs: results)
    monkeypatch.setattr(search, "auto_play_enabled", lambda: True)
    monkeypatch.setattr(search, "clean_auto_play_undesired", lambda results: results)
    monkeypatch.setattr(search, "get_setting", lambda key, default=None: "1080p" if key == "auto_play_quality" else default)
    monkeypatch.setattr(search, "JacktookPLayer", FakePlayer)
    monkeypatch.setattr(search, "is_youtube_addon_enabled", lambda: False, raising=False)

    search.run_search_entry(
        {
            "query": "Movie",
            "mode": "movies",
            "media_type": "movies",
            "ids": '{"imdb_id": "tt123"}',
        }
    )

    assert len(played) == 1
    assert played[0]["url"].startswith("https://media.example/movie.mkv|")
    assert played[0]["stream_subtitles"] == source.streamSubtitles
    assert played[0]["file_idx"] == 2
    assert played[0]["headers"] == {"Referer": "https://media.example"}


def test_show_source_select_preserves_the_canonical_stremio_payload(monkeypatch):
    client = _stremio_addon_client(monkeypatch)
    source = client.parse_response(_stremio_response({"streams": [_stremio_stream_data()]}))[0]
    shown = []

    monkeypatch.setattr(search, "build_media_metadata", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(search, "is_youtube_addon_enabled", lambda: False)
    monkeypatch.setattr(
        search,
        "source_select",
        lambda _item_info, xml_file, sources: shown.extend(sources) or bool(xml_file),
    )

    assert search.show_source_select(
        [source], "movies", {"imdb_id": "tt123"}, {}, "Movie", "movies", False
    ) is True
    assert len(shown) == 1
    payload = payload_from_torrent(shown[0])
    assert payload["stream_subtitles"] == source.streamSubtitles
    assert payload["file_idx"] == 2
    assert payload["headers"] == {"Referer": "https://media.example"}


def test_parse_response_returns_no_sources_for_a_malformed_legacy_cache(monkeypatch):
    client = _stremio_addon_client(monkeypatch)
    malformed_response = _stremio_response({"streams": [object()]})

    assert client.parse_response(malformed_response, is_external_cache=True) == []


def test_super_quick_play_preserves_metadata_from_a_legacy_stremio_cache(monkeypatch):
    source = TorrentStream(
        title="Cached movie",
        type="direct",
        addonKey="org.example.addon|https://example.com",
        url="https://media.example/movie.mkv",
        streamSubtitles=[{"id": "sub-en", "url": "https://sub.example/en.vtt", "lang": "eng"}],
        stremioMetadata={
            "url": "https://media.example/movie.mkv",
            "fileIdx": 2,
            "sources": [TRACKER_B],
            "trackers": [TRACKER_A],
            "subtitles": [
                {"id": "sub-en", "url": "https://sub.example/en.vtt", "lang": "eng"}
            ],
            "behaviorHints": {
                "filename": "Movie.1080p.mkv",
                "videoSize": 123456,
                "proxyHeaders": {"request": {"Referer": "https://media.example"}},
            },
        },
    )
    played = []

    class FakePlayer:
        def run(self, data):
            played.append(data)

    monkeypatch.setattr(search, "get_setting", lambda key, default=None: {
        "super_quick_play": True,
        "silent_resume": True,
    }.get(key, default))
    monkeypatch.setattr(search.cache, "get", lambda _key: source)
    monkeypatch.setattr(search, "JacktookPLayer", FakePlayer)
    monkeypatch.setattr(search, "is_youtube_addon_enabled", lambda: False, raising=False)

    assert search._handle_super_quick_play({"ids": '{"imdb_id": "tt123"}'}) is True
    assert played[0]["stream_subtitles"] == source.streamSubtitles
    assert played[0]["file_idx"] == 2
    assert played[0]["headers"] == {"Referer": "https://media.example"}


def test_super_quick_play_reports_legacy_cache_failure_before_player(monkeypatch):
    notifications = []
    source = {
        "title": "Unsupported cached source",
        "type": "direct",
        "addonKey": "org.example.addon|https://example.com",
        "externalUrl": "https://external.example/watch",
        "streamSubtitles": [{"url": "https://sub.example/en.vtt", "lang": "eng"}],
    }

    class UnexpectedPlayer:
        def __init__(self):
            raise AssertionError("unsupported cached source reached the player")

    monkeypatch.setattr(search, "get_setting", lambda key, default=None: {
        "super_quick_play": True,
        "silent_resume": True,
    }.get(key, default))
    monkeypatch.setattr(search.cache, "get", lambda _key: source)
    monkeypatch.setattr(search, "notification", lambda message: notifications.append(message))
    monkeypatch.setattr(search, "JacktookPLayer", UnexpectedPlayer)
    monkeypatch.setattr(search, "is_youtube_addon_enabled", lambda: False, raising=False)

    assert search._handle_super_quick_play({"ids": '{"imdb_id": "tt123"}'}) is True
    assert notifications == ["External web pages are not playable sources."]


def test_show_source_select_rejects_unsupported_stremio_sources_before_dialog(monkeypatch):
    shown = []
    source = TorrentStream(
        title="Unsupported source",
        addonKey="org.example.addon|https://example.com",
        stremioMetadata={"externalUrl": "https://external.example/watch"},
    )
    notifications = []

    monkeypatch.setattr(search, "notification", lambda message: notifications.append(message))
    monkeypatch.setattr(search, "is_youtube_addon_enabled", lambda: False, raising=False)
    monkeypatch.setattr(search, "build_media_metadata", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        search,
        "source_select",
        lambda *_args, **_kwargs: shown.append(True) or True,
    )

    assert search.show_source_select(
        [source], "movies", {"imdb_id": "tt123"}, {}, "Movie", "movies", False
    ) is False
    assert shown == []
    assert notifications == ["External web pages are not playable sources."]


def _catalog_params(**overrides):
    params = {
        "addon_url": "https://example.com/addon",
        "catalog_type": "movie",
        "meta_id": "custom:movie",
        "ids": json.dumps({"imdb_id": "tt123"}),
        "poster": "poster.jpg",
        "fanart": "fanart.jpg",
        "genres": json.dumps(["Drama"]),
        "overview": "Catalog overview",
    }
    params.update(overrides)
    return params


def _capture_catalog_builder(monkeypatch, builder, response, params):
    captured = []
    monkeypatch.setattr(catalog_menus, "catalogs_get_cache", lambda *args, **kwargs: response)
    monkeypatch.setattr(catalog_menus, "notification", lambda *args, **kwargs: None)
    monkeypatch.setattr(catalog_menus, "end_of_directory", lambda *args, **kwargs: None)
    monkeypatch.setattr(catalog_menus, "make_list_item", lambda label="": MagicMock())
    monkeypatch.setattr(
        catalog_menus,
        "add_directory_items_batch",
        lambda items: captured.extend(json.loads(item[0].split("data=", 1)[1]) for item in items),
    )
    monkeypatch.setattr(
        catalog_menus,
        "build_url",
        lambda action, **kwargs: f"{action}?data={kwargs['data']}",
    )

    builder(params)
    return captured


def test_catalog_movie_preserves_canonical_fields_and_skips_unsupported(monkeypatch):
    stream = Stream.from_dict(
        {
            "url": "https://media.example/movie.mkv",
            "infoHash": INFO_HASH,
            "fileIdx": 2,
            "title": "Movie 1080p",
            "description": "Stream plot",
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
    stream.stremio_metadata = {"provider": "canonical"}
    response = {
        "streams": [
            stream,
            {"url": "javascript:alert(1)", "title": "Malformed"},
            {"externalUrl": "https://external.example/watch", "title": "External"},
        ]
    }

    captured = _capture_catalog_builder(
        monkeypatch, catalog_menus.list_stremio_movie, response, _catalog_params()
    )

    assert len(captured) == 1
    assert captured[0]["url"] == "https://media.example/movie.mkv"
    assert captured[0]["type"] == catalog_menus.IndexerType.DIRECT
    assert captured[0]["info_hash"] == INFO_HASH
    assert captured[0]["file_idx"] == 2
    assert captured[0]["sources"] == [TRACKER_B]
    assert captured[0]["trackers"] == [TRACKER_A]
    assert captured[0]["headers"] == {"Referer": "https://media.example"}
    assert captured[0]["filename"] == "Movie.1080p.mkv"
    assert captured[0]["size"] == 123456
    assert captured[0]["videoHash"] == "video-hash"
    assert captured[0]["stream_subtitles"] == [
        {"id": "sub-en", "url": "https://sub.example/en.vtt", "lang": "eng"}
    ]
    assert captured[0]["stremio_metadata"]["provider"] == "canonical"


def test_catalog_youtube_handoff_uses_safe_plugin_url_and_addon_gate(monkeypatch):
    monkeypatch.setattr(catalog_menus, "is_youtube_addon_enabled", lambda: True)
    captured = _capture_catalog_builder(
        monkeypatch,
        catalog_menus.list_stremio_movie,
        {"streams": [{"ytId": "video/id", "title": "YouTube trailer"}]},
        _catalog_params(),
    )
    assert captured[0]["ytId"] == "video/id"
    assert captured[0]["url"] == "plugin://plugin.video.youtube/play/?video_id=video%2Fid"

    monkeypatch.setattr(catalog_menus, "is_youtube_addon_enabled", lambda: False)
    assert catalog_menus._stremio_catalog_playback_data(
        {"ytId": "video/id"}, _catalog_params()
    ) is None


def test_catalog_skips_incomplete_object_without_aborting_valid_candidates(monkeypatch):
    class IncompleteStream:
        @property
        def url(self):
            raise RuntimeError

    captured = _capture_catalog_builder(
        monkeypatch,
        catalog_menus.list_stremio_movie,
        {"streams": [IncompleteStream(), {"url": "https://media.example/ok.mkv"}]},
        _catalog_params(),
    )

    assert len(captured) == 1
    assert captured[0]["url"] == "https://media.example/ok.mkv"

def test_catalog_tv_preserves_hash_payload_and_accepts_dict_streams(monkeypatch):
    response = {
        "streams": [
            {
                "infoHash": INFO_HASH,
                "title": "Episode torrent",
                "description": "Episode plot",
                "sources": [TRACKER_A],
                "trackers": [TRACKER_B],
                "subtitles": [{"url": "https://sub.example/episode.vtt", "lang": "eng"}],
            },
            {"externalUrl": "https://external.example/watch", "title": "Unsupported"},
        ]
    }

    captured = _capture_catalog_builder(
        monkeypatch, catalog_menus.list_stremio_tv, response, _catalog_params(catalog_type="series")
    )

    assert len(captured) == 1
    assert captured[0]["info_hash"] == INFO_HASH
    assert captured[0]["magnet"] == f"magnet:?xt=urn:btih:{INFO_HASH}"
    assert captured[0]["is_torrent"] is True
    assert captured[0]["sources"] == [TRACKER_A]
    assert captured[0]["trackers"] == [TRACKER_B]
    assert captured[0]["subtitles"] == [
        {"url": "https://sub.example/episode.vtt", "lang": "eng"}
    ]


def test_catalog_tv_streams_handles_dicts_and_malformed_candidates(monkeypatch):
    magnet = f"magnet:?xt=urn:btih:{INFO_HASH}&tr={TRACKER_A}"
    captured = []
    monkeypatch.setattr(catalog_menus, "end_of_directory", lambda *args, **kwargs: None)
    monkeypatch.setattr(catalog_menus, "make_list_item", lambda label="": MagicMock())
    monkeypatch.setattr(
        catalog_menus,
        "add_directory_items_batch",
        lambda items: captured.extend(items),
    )
    monkeypatch.setattr(
        catalog_menus,
        "build_url",
        lambda action, **kwargs: f"{action}?data={kwargs['data']}",
    )

    catalog_menus.list_stremio_tv_streams(
        _catalog_params(
            streams=json.dumps(
                [
                    {
                        "url": magnet,
                        "name": "Episode magnet",
                        "sources": [TRACKER_B],
                        "subtitles": [{"url": "https://sub.example/episode.vtt", "lang": "eng"}],
                    },
                    {"url": "not-a-playable-url", "name": "Malformed"},
                    {"name": "Missing locator"},
                ]
            )
        )
    )

    assert len(captured) == 1
    data = json.loads(captured[0][0].split("data=", 1)[1])
    assert data["url"] == magnet
    assert data["magnet"] == magnet
    assert data["sources"] == [TRACKER_B]
    assert data["stream_subtitles"] == [
        {"url": "https://sub.example/episode.vtt", "lang": "eng"}
    ]


def test_catalog_url_encodes_manifest_declared_extra_args(monkeypatch):
    client = addon_client.StremioAddonCatalogsClient(
        {"addon_url": "https://example.com/addon", "catalog_type": "movie", "catalog_id": "popular"}
    )
    captured = {}

    class _Response:
        status_code = 200

        def json(self):
            return {"metas": []}

    monkeypatch.setattr(
        client.session,
        "get",
        lambda url, **kwargs: captured.update(url=url) or _Response(),
    )
    monkeypatch.setattr(addon_client, "get_int_setting", lambda _key: 7)

    assert client.get_catalog_info(search="Spider & Friends", sort="top/rated") == {"metas": []}
    assert captured["url"] == (
        "https://example.com/addon/catalog/movie/popular/search=Spider%20%26%20Friends"
        "/sort=top%2Frated.json"
    )


def test_preferred_video_streams_precede_normal_search_without_replacing_it(monkeypatch):
    preferred = {
        "url": "https://media.example/episode.mkv",
        "behaviorHints": {"filename": "Episode.mkv", "videoHash": "video-hash", "videoSize": 123},
    }
    normal = TorrentStream(title="Jackett result", url="magnet:?xt=urn:btih:" + INFO_HASH)
    captured = {}

    monkeypatch.setattr(search, "_handle_super_quick_play", lambda _params: False)
    monkeypatch.setattr(search, "set_content_type", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(search, "set_watched_title", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(search, "search_client", lambda *args, **kwargs: [normal])
    monkeypatch.setattr(search, "_process_search_results", lambda results, *_args, **_kwargs: results)
    monkeypatch.setattr(search, "auto_play_enabled", lambda: False)
    monkeypatch.setattr(
        search,
        "show_source_select",
        lambda results, *_args, **_kwargs: captured.setdefault("results", results) or True,
    )

    search.run_search_entry(
        {
            "query": "Show",
            "mode": "tv",
            "media_type": "tv",
            "ids": '{"imdb_id": "tt123"}',
            "preferred_stremio_streams": json.dumps([preferred]),
        }
    )

    assert [source.title for source in captured["results"]] == ["Episode.mkv", "Jackett result"]
    assert captured["results"][0].stremioMetadata == preferred


def test_episode_navigation_orders_default_video_and_passes_its_streams(monkeypatch):
    first = Video(id="first", title="First", released="", season=1, episode=1)
    second = Video(
        id="second",
        title="Second",
        released="",
        season=1,
        episode=2,
        streams=[Stream.from_dict({"url": "https://media.example/default.mkv"})],
    )
    meta = Meta(
        id="custom:show",
        type="series",
        name="",
        videos=[first, second],
        behaviorHints=MetaBehaviorHints(defaultVideoId="second"),
    )
    urls = []

    class _ListItem:
        def getVideoInfoTag(self):
            return self

        def __getattr__(self, _name):
            return lambda *args, **kwargs: None

    monkeypatch.setattr(catalog_menus, "catalogs_get_cache", lambda *args: {"meta": meta})
    monkeypatch.setattr(catalog_menus, "get_addon_by_base_url", lambda *_args: None)
    monkeypatch.setattr(catalog_menus, "addon_has_stream", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(catalog_menus, "make_list_item", lambda *args, **kwargs: _ListItem())
    monkeypatch.setattr(catalog_menus, "add_directory_items_batch", lambda *_args: None)
    monkeypatch.setattr(catalog_menus, "end_of_directory", lambda: None)
    monkeypatch.setattr(catalog_menus, "_append_context_menu_items", lambda *_args: None)
    monkeypatch.setattr(catalog_menus, "kodi_play_media", lambda **_kwargs: "search")
    monkeypatch.setattr(
        catalog_menus,
        "build_url",
        lambda action, **kwargs: urls.append((action, kwargs)) or action,
    )

    catalog_menus.list_stremio_episodes(
        {"addon_url": "https://addon.example", "catalog_type": "series", "meta_id": "custom:show", "season": 1}
    )

    assert [json.loads(kwargs["preferred_stremio_streams"]) for _, kwargs in urls] == [
        [{"url": "https://media.example/default.mkv", "ytId": None, "infoHash": None, "fileIdx": None, "externalUrl": None, "name": None, "title": None, "description": None, "behaviorHints": None, "subtitles": [], "fileMustInclude": None, "nzbUrl": None, "servers": [], "rarUrls": [], "zipUrls": [], "sevenZipUrls": [], "tgzUrls": [], "tarUrls": [], "meta": {}, "sources": [], "trackers": []}],
        [],
    ]
    assert [kwargs["scoped_addon_url"] for _, kwargs in urls] == ["", "https://addon.example"]
