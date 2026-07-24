import json
from unittest.mock import MagicMock

import pytest

from lib import navigation, search
from lib.api.stremio.addon_manager import AddonManager
from lib.api.stremio.models import Meta, MetaBehaviorHints, Stream, Video
from lib.clients.stremio import addon_client, catalog_menus
from lib.clients.stremio import playback as stremio_playback
from lib.clients.stremio.playback import (
    StremioPlaybackError,
    candidate_from_payload,
    classify,
    normalize_stream,
    payload_from_torrent,
    resolve,
)
from lib.domain.torrent import TorrentStream
from lib.gui import source_pack_select
from lib.gui import source_select as source_select_module
from lib.utils.general.utils import DebridType, IndexerType, Players
from lib.utils.player import utils as player_utils

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


def _assert_stremio_runtime_rejected_before_resolution(monkeypatch, data):
    resolvers = [MagicMock() for _ in range(5)]
    debrid_resolver, jacktorr_resolver, torrest_resolver, elementum_resolver, picker = resolvers
    monkeypatch.setattr(player_utils, "get_debrid_url", debrid_resolver)
    monkeypatch.setattr(player_utils, "get_jacktorr_url", jacktorr_resolver)
    monkeypatch.setattr(player_utils, "get_torrest_url", torrest_resolver)
    monkeypatch.setattr(player_utils, "get_elementum_url", elementum_resolver)
    monkeypatch.setattr(player_utils, "get_torrent_client_selection", picker)

    assert stremio_playback.resolve_stremio_playback_url(data) is None
    for resolver in resolvers:
        resolver.assert_not_called()


def test_source_select_preserves_indexed_stremio_metadata_for_runtime_revalidation(monkeypatch):
    source = TorrentStream(
        type=IndexerType.TORRENT,
        indexer="Stremio",
        infoHash=INFO_HASH,
        url=f"magnet:?xt=urn:btih:{INFO_HASH}",
        stremioMetadata={"fileIdx": 3},
    )
    source_select = source_select_module.SourceSelect.__new__(source_select_module.SourceSelect)
    source_select.item_information = {}
    prepared = source_select.prepare_source_data(source, source.url, source.url, True)

    assert prepared["stremio_metadata"] == {"fileIdx": 3}
    monkeypatch.setattr(player_utils, "resolve_playback_url", lambda data: data)
    assert stremio_playback.resolve_stremio_playback_url(prepared)["file_idx"] == 3
    assert source_select._ensure_playback_info(source)["file_idx"] == 3


def test_prepare_source_data_preserves_stremio_security_markers():
    source = TorrentStream(
        debridType=DebridType.RD,
        stremioMetadata={"fileIdx": "invalid", "_invalid_stremio_metadata": True},
    )
    source_select = source_select_module.SourceSelect.__new__(source_select_module.SourceSelect)
    source_select.item_information = {}

    prepared = source_select.prepare_source_data(source, "", "", False)

    assert prepared["debrid_type"] == DebridType.RD
    assert prepared["stremio_metadata"] == source.stremioMetadata


def test_base_window_marks_invalid_stremio_metadata_for_runtime_revalidation(monkeypatch):
    source = TorrentStream(stremioMetadata="malformed")
    source_select = source_select_module.SourceSelect.__new__(source_select_module.SourceSelect)
    source_select.item_information = {}
    resolver_calls = []

    prepared = source_select.prepare_source_data(source, "", "", False)
    monkeypatch.setattr(
        player_utils, "resolve_playback_url", lambda data: resolver_calls.append(data) or data
    )

    assert prepared["stremio_metadata"] == {"_invalid_stremio_metadata": True}
    assert stremio_playback.resolve_stremio_playback_url(prepared) is None
    assert resolver_calls == []


def test_base_window_treats_absent_stremio_metadata_as_clean(monkeypatch):
    source = TorrentStream(stremioMetadata=None)
    source_select = source_select_module.SourceSelect.__new__(source_select_module.SourceSelect)
    source_select.item_information = {}
    resolver_calls = []

    prepared = source_select.prepare_source_data(source, "", "", False)
    monkeypatch.setattr(
        player_utils, "resolve_playback_url", lambda data: resolver_calls.append(data) or data
    )

    assert "stremio_metadata" not in prepared
    assert stremio_playback.resolve_stremio_playback_url(prepared) == prepared
    assert resolver_calls == [prepared]


def test_pack_selection_treats_absent_stremio_metadata_as_clean(monkeypatch):
    source = TorrentStream(type=IndexerType.TORRENT, stremioMetadata=None)
    selector = source_pack_select.SourcePackSelect.__new__(source_pack_select.SourcePackSelect)
    selector.source = source
    selector.pack_info = {"files": [("https://media.example/episode.mkv", "Episode 1")]}
    selector.item_information = {}
    selector.position = 0
    selector.playback_info = None
    selector.setProperty = lambda *_args: None
    selector.close = lambda: None
    resolver_calls = []
    monkeypatch.setattr(
        player_utils, "resolve_playback_url", lambda data: resolver_calls.append(data) or data
    )

    selector._resolve_item()

    assert selector.playback_info["pack_info"]["url"] == "https://media.example/episode.mkv"
    assert "stremio_metadata" not in resolver_calls[0]


@pytest.mark.parametrize(
    ("debrid_type", "settings"),
    [
        ("", {"torrent_enable": False, "torrent_client": Players.JACKTORR}),
        (DebridType.RD, {"torrent_enable": True, "torrent_client": Players.JACKTORR}),
    ],
    ids=["configuration_changed", "debrid_intent"],
)
def test_pack_selection_revalidates_stremio_metadata_before_legacy_resolution(
    monkeypatch, debrid_type, settings
):
    source = TorrentStream(
        type=IndexerType.TORRENT,
        debridType=debrid_type,
        stremioMetadata={"fileIdx": 3},
    )
    selector = source_pack_select.SourcePackSelect.__new__(source_pack_select.SourcePackSelect)
    selector.source = source
    selector.pack_info = {
        "files": [("file-id", "Episode 1")],
        "torrent_id": "torrent-id",
    }
    selector.item_information = {}
    selector.position = 0
    selector.playback_info = None
    selector.setProperty = lambda *_args: None
    selector.close = lambda: None
    resolver_calls = []

    monkeypatch.setattr(
        player_utils, "resolve_playback_url", lambda data: resolver_calls.append(data) or data
    )

    selector._resolve_item()

    assert selector.playback_info is None
    assert resolver_calls == []


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
    monkeypatch.setattr(search, "current_stremio_playback_capabilities", lambda: {})
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

    monkeypatch.setattr(search, "current_stremio_playback_capabilities", lambda: {})
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


def test_trackerless_info_hash_reaches_external_torrent_client(monkeypatch):
    captured = {}

    def resolve_with_client(magnet, url, mode, ids, client="", data=None):
        captured.update(
            magnet=magnet,
            url=url,
            mode=mode,
            ids=ids,
            client=client,
            data=data,
        )
        return "plugin://torrent-client/play"

    preferred = {"infoHash": INFO_HASH, "title": "Trackerless torrent"}
    source = search._preferred_stremio_results([preferred])[0]
    payload = resolve(candidate_from_payload(payload_from_torrent(source)))

    monkeypatch.setattr(player_utils, "get_setting", lambda key: key == "torrent_enable")
    monkeypatch.setattr(player_utils, "get_torrent_url_for_client", resolve_with_client)

    assert source.type == IndexerType.TORRENT
    assert player_utils.resolve_playback_url(payload)["url"] == "plugin://torrent-client/play"
    assert captured["magnet"] == f"magnet:?xt=urn:btih:{INFO_HASH}"
    assert captured["url"] == f"magnet:?xt=urn:btih:{INFO_HASH}"


def test_malformed_info_hash_remains_rejected():
    decision = classify(normalize_stream({"infoHash": "not-a-valid-hash"}))

    assert decision.supported is False
    assert decision.code == "malformed_locator"


@pytest.mark.parametrize(
    ("tracker", "expected_code"),
    [
        ("not-a-tracker-url", "malformed_tracker"),
        ("https://user:password@tracker.example/announce", "unsafe_locator"),
        ("https://tracker.example/announce|unsafe", "unsafe_locator"),
    ],
)
def test_trackerless_torrents_reject_malformed_or_unsafe_trackers(tracker, expected_code):
    decision = classify(normalize_stream({"infoHash": INFO_HASH, "trackers": [tracker]}))

    assert decision.supported is False
    assert decision.code == expected_code


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


def test_stremio_indexed_torrent_reaches_legacy_resolution(monkeypatch):
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

    search._resolve_stremio_source(source, {"is_torrent": False})

    assert legacy_calls
    assert legacy_calls[0]["file_idx"] == 3


def test_stremio_indexed_debrid_torrent_reaches_legacy_resolution(
    monkeypatch,
):
    source = {
        "addonKey": "org.example.addon|https://example.com",
        "info_hash": INFO_HASH,
        "magnet": f"magnet:?xt=urn:btih:{INFO_HASH}",
        "stremioMetadata": {"title": "Benign metadata"},
        "stremio_metadata": {"fileIdx": 3, "debridType": DebridType.RD},
    }
    resolver_calls = []

    monkeypatch.setattr(
        search, "resolve_playback_url", lambda data: resolver_calls.append(data) or data
    )

    search._resolve_stremio_source(source)

    assert resolver_calls
    assert resolver_calls[0]["debrid_type"] == DebridType.RD


@pytest.mark.parametrize("metadata_key", ["stremio_metadata", "stremioMetadata"])
def test_malformed_nested_metadata_with_top_level_file_index_rejects_before_resolution(
    monkeypatch, metadata_key
):
    source = {
        "addonKey": "org.example.addon|https://example.com",
        "info_hash": INFO_HASH,
        "magnet": f"magnet:?xt=urn:btih:{INFO_HASH}",
        "file_idx": 3,
        metadata_key: "malformed",
    }
    resolver_calls = []

    monkeypatch.setattr(
        search,
        "get_setting",
        lambda setting: {"torrent_enable": True, "torrent_client": Players.JACKTORR}.get(setting),
    )
    monkeypatch.setattr(
        search, "resolve_playback_url", lambda data: resolver_calls.append(data) or data
    )

    with pytest.raises(StremioPlaybackError) as error:
        search._resolve_stremio_source(source)

    assert error.value.code == "unsafe_metadata"
    assert resolver_calls == []


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


def test_valid_file_index_does_not_reject_torrent_resolution():
    candidate = normalize_stream(_supported_hash_payload(fileIdx=3))

    decision = classify(candidate, {"client": "torrest"})
    assert decision.source_class == "torrent_hash"
    assert decision.supported


@pytest.mark.parametrize(
    "payload",
    [
        {"url": "https://media.example/movie.mkv", "fileIdx": 3, "debridType": DebridType.RD},
        {"ytId": "youtube-video-id", "file_idx": 3, "debrid_type": DebridType.RD},
    ],
    ids=["direct_http", "youtube"],
)
def test_indexed_direct_sources_with_debrid_intent_are_rejected(payload):
    decision = classify(normalize_stream(payload))

    assert decision.source_class == "unsupported"
    assert decision.code == "file_index_unsupported"


@pytest.mark.parametrize(
    "payload, context",
    [
        (
            {
                "url": "https://media.example/movie.mkv",
                "fileIdx": 3,
                "debridType": "",
                "_stremio_debrid_intent": True,
            },
            {},
        ),
        (
            {
                "ytId": "youtube-video-id",
                "file_idx": 3,
                "debrid_type": "unknown",
                "_stremio_debrid_intent": True,
            },
            {"available_addons": {"plugin.video.youtube"}},
        ),
    ],
    ids=["direct_http_empty", "youtube_invalid"],
)
def test_indexed_direct_sources_with_malformed_debrid_intent_do_not_resolve(
    monkeypatch, payload, context
):
    resolver_calls = []
    monkeypatch.setattr(
        stremio_playback,
        "_payload_from_candidate",
        lambda candidate: resolver_calls.append(candidate) or {},
    )

    with pytest.raises(StremioPlaybackError) as error:
        resolve(normalize_stream(payload), context)

    assert error.value.code == "file_index_unsupported"
    assert resolver_calls == []


@pytest.mark.parametrize(
    "payload",
    [
        {"info_hash": INFO_HASH, "fileIdx": 1, "file_idx": 2},
        {
            "info_hash": INFO_HASH,
            "stremio_metadata": {"fileIdx": 1, "file_idx": 2},
        },
    ],
    ids=["top_level", "nested_metadata"],
)
def test_conflicting_file_index_aliases_do_not_invoke_torrent_resolver(monkeypatch, payload):
    resolver_calls = []
    decision = classify(normalize_stream(payload))
    monkeypatch.setattr(
        player_utils, "get_torrent_url", lambda *args, **kwargs: resolver_calls.append(args)
    )

    assert decision.code == "malformed_locator"
    assert stremio_playback.resolve_stremio_playback_url(payload) is None
    assert resolver_calls == []


def test_stale_jacktorr_settings_do_not_block_indexed_torrent(monkeypatch):
    source = {
        "addonKey": "org.example.addon|https://example.com",
        "stremioMetadata": _supported_hash_payload(fileIdx=3),
    }
    resolver_calls = []

    monkeypatch.setattr(
        search,
        "get_setting",
        lambda setting: {"torrent_enable": True, "torrent_client": Players.JACKTORR}.get(setting),
    )
    monkeypatch.setattr(
        search, "resolve_playback_url", lambda data: resolver_calls.append(data) or data
    )

    search._resolve_stremio_source(source)

    assert resolver_calls


def test_jacktorr_configured_and_enabled_routes_indexed_torrent_to_its_selector(monkeypatch):
    source = {
        "addonKey": "org.example.addon|https://example.com",
        "stremioMetadata": _supported_hash_payload(fileIdx=3),
    }
    captured = []

    monkeypatch.setattr(
        search,
        "get_setting",
        lambda setting: {"torrent_enable": True, "torrent_client": Players.JACKTORR}.get(setting),
    )
    monkeypatch.setattr(
        player_utils,
        "get_jacktorr_url",
        lambda magnet, url, data=None: captured.append((magnet, url, data)) or "plugin://jacktorr/selector",
    )
    monkeypatch.setattr(player_utils, "get_setting", search.get_setting)

    resolved = search._resolve_stremio_source(source)

    assert resolved["url"] == "plugin://jacktorr/selector"
    assert "file_idx" not in captured[0][2]
    assert "fileIdx" not in captured[0][2]


def test_unavailable_jacktorr_does_not_preempt_normal_resolution(monkeypatch):
    source = {
        "addonKey": "org.example.addon|https://example.com",
        "stremioMetadata": _supported_hash_payload(fileIdx=3),
    }
    resolver_calls = []

    monkeypatch.setattr(
        search,
        "get_setting",
        lambda setting: {"torrent_enable": True, "torrent_client": Players.JACKTORR}.get(setting),
    )
    monkeypatch.setattr(
        search,
        "resolve_playback_url",
        lambda data: resolver_calls.append(data) or data,
    )

    search._resolve_stremio_source(source)

    assert resolver_calls


@pytest.mark.parametrize(
    ("settings", "addon_enabled"),
    [
        ({"torrent_enable": False, "torrent_client": Players.JACKTORR}, True),
        ({"torrent_enable": True, "torrent_client": Players.TORREST}, True),
        ({"torrent_enable": True, "torrent_client": Players.ELEMENTUM}, True),
        ({"torrent_enable": True, "torrent_client": Players.JACKGRAM}, True),
        ({"torrent_enable": True, "torrent_client": Players.JACKTORR}, False),
    ],
    ids=["torrent_disabled", "torrest", "elementum", "jackgram", "jacktorr_unavailable"],
)
def test_indexed_torrent_reaches_normal_resolution_regardless_of_client(
    monkeypatch, settings, addon_enabled
):
    source = {
        "addonKey": "org.example.addon|https://example.com",
        "stremioMetadata": _supported_hash_payload(fileIdx=3),
    }
    resolver_calls = []

    monkeypatch.setattr(search, "get_setting", lambda setting: settings.get(setting))
    monkeypatch.setattr(
        search, "resolve_playback_url", lambda data: resolver_calls.append(data) or data
    )

    search._resolve_stremio_source(source)

    assert resolver_calls


@pytest.mark.parametrize("debrid_type", DebridType.values())
def test_indexed_torrent_debrid_route_reaches_debrid_resolution(
    monkeypatch, debrid_type
):
    source = {
        "addonKey": "org.example.addon|https://example.com",
        "stremioMetadata": _supported_hash_payload(fileIdx=3, debridType=debrid_type),
    }
    debrid_calls = []

    monkeypatch.setattr(
        search,
        "get_setting",
        lambda setting: {"torrent_enable": True, "torrent_client": Players.JACKTORR}.get(setting),
    )
    monkeypatch.setattr(
        search,
        "resolve_playback_url",
        lambda data: debrid_calls.append(data) or data,
    )

    search._resolve_stremio_source(source)

    assert debrid_calls
    assert debrid_calls[0]["debrid_type"] == debrid_type


@pytest.mark.parametrize(
    ("metadata_key", "debrid_key"),
    [
        (None, "debrid_type"),
        (None, "debridType"),
        ("stremioMetadata", "debrid_type"),
        ("stremioMetadata", "debridType"),
        ("stremio_metadata", "debrid_type"),
        ("stremio_metadata", "debridType"),
    ],
    ids=[
        "top_level_snake_case",
        "top_level_camel_case",
        "camel_metadata_snake_case",
        "camel_metadata_camel_case",
        "snake_metadata_snake_case",
        "snake_metadata_camel_case",
    ],
)
@pytest.mark.parametrize(
    "debrid_value",
    ["", 0, False, [], {}, None],
    ids=["empty_string", "zero", "false", "list", "mapping", "none"],
)
def test_indexed_torrent_with_debrid_metadata_reaches_existing_resolution(
    monkeypatch, metadata_key, debrid_key, debrid_value
):
    source = {
        "addonKey": "org.example.addon|https://example.com",
        "stremioMetadata": _supported_hash_payload(fileIdx=3),
    }
    if metadata_key:
        source[metadata_key] = _supported_hash_payload(fileIdx=3)
        source[metadata_key][debrid_key] = debrid_value
    else:
        source[debrid_key] = debrid_value
    resolver_calls = []

    monkeypatch.setattr(
        search,
        "get_setting",
        lambda setting: {"torrent_enable": True, "torrent_client": Players.JACKTORR}.get(setting),
    )
    monkeypatch.setattr(
        search, "resolve_playback_url", lambda data: resolver_calls.append(data) or data
    )

    search._resolve_stremio_source(source)

    assert resolver_calls


@pytest.mark.parametrize("file_idx", [-1, True, "3"])
def test_malformed_file_index_remains_rejected(file_idx):
    candidate = normalize_stream(_supported_hash_payload(fileIdx=file_idx))

    decision = classify(candidate)

    assert decision.source_class == "unsupported"
    assert decision.code == "malformed_locator"


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
    source = client.parse_response(
        _stremio_response({"streams": [_stremio_stream_data(fileIdx=None)]})
    )[0]
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
    assert played[0]["file_idx"] is None
    assert played[0]["headers"] == {"Referer": "https://media.example"}


def test_show_source_select_preserves_the_canonical_stremio_payload(monkeypatch):
    client = _stremio_addon_client(monkeypatch)
    source = client.parse_response(
        _stremio_response({"streams": [_stremio_stream_data(fileIdx=None)]})
    )[0]
    shown = []

    monkeypatch.setattr(search, "build_media_metadata", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(search, "current_stremio_playback_capabilities", lambda: {})
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
    assert payload["file_idx"] is None
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
    assert played[0]["file_idx"] is None
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


def test_show_source_select_preserves_valid_indexed_torrents(monkeypatch):
    shown = []
    notifications = []
    rejected = TorrentStream(
        title="Indexed torrent",
        addonKey="org.example.addon|https://example.com",
        stremioMetadata=_supported_hash_payload(fileIdx=3),
    )
    valid = TorrentStream(
        title="Direct stream",
        addonKey="org.example.addon|https://example.com",
        stremioMetadata={"url": "https://media.example/movie.mkv"},
    )

    monkeypatch.setattr(search, "notification", notifications.append)
    monkeypatch.setattr(search, "current_stremio_playback_capabilities", lambda: {})
    monkeypatch.setattr(search, "build_media_metadata", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        search,
        "source_select",
        lambda *_args, **kwargs: shown.extend(kwargs["sources"]) or True,
    )

    assert search.show_source_select(
        [rejected, valid], "movies", {"imdb_id": "tt123"}, {}, "Movie", "movies", False
    ) is True
    assert shown == [rejected, valid]
    assert notifications == []


def test_show_source_select_preserves_trackerless_torrents_without_notification(monkeypatch):
    shown = []
    notifications = []
    trackerless = TorrentStream(
        title="Trackerless torrent",
        addonKey="org.example.addon|https://example.com",
        stremioMetadata={"infoHash": INFO_HASH},
    )
    valid = TorrentStream(
        title="Direct stream",
        addonKey="org.example.addon|https://example.com",
        stremioMetadata={"url": "https://media.example/movie.mkv"},
    )

    monkeypatch.setattr(search, "notification", notifications.append)
    monkeypatch.setattr(search, "current_stremio_playback_capabilities", lambda: {})
    monkeypatch.setattr(search, "build_media_metadata", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        search,
        "source_select",
        lambda *_args, **kwargs: shown.extend(kwargs["sources"]) or True,
    )

    assert search.show_source_select(
        [trackerless, valid], "movies", {"imdb_id": "tt123"}, {}, "Movie", "movies", False
    ) is True
    assert shown == [trackerless, valid]
    assert notifications == []


def test_preferred_trackerless_stream_uses_external_torrent_client_contract():
    preferred = {"infoHash": INFO_HASH, "title": "Trackerless torrent"}

    results = search._preferred_stremio_results([preferred])

    assert len(results) == 1
    assert results[0].type == IndexerType.TORRENT
    assert results[0].infoHash == INFO_HASH
    assert results[0].url == f"magnet:?xt=urn:btih:{INFO_HASH}"


def test_show_source_select_preserves_all_valid_indexed_torrents(monkeypatch):
    shown = []
    notifications = []
    rejected = TorrentStream(
        title="Indexed torrent",
        addonKey="org.example.addon|https://example.com",
        stremioMetadata=_supported_hash_payload(fileIdx=3),
    )

    monkeypatch.setattr(search, "notification", notifications.append)
    monkeypatch.setattr(search, "current_stremio_playback_capabilities", lambda: {})
    monkeypatch.setattr(search, "source_select", lambda *_args, **_kwargs: shown.append(True) or True)

    monkeypatch.setattr(search, "build_media_metadata", lambda *_args, **_kwargs: {})

    assert search.show_source_select(
        [rejected, rejected], "movies", {"imdb_id": "tt123"}, {}, "Movie", "movies", False
    ) is True
    assert shown == [True]
    assert notifications == []


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
    assert "file_idx" not in captured[0]
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


def test_catalog_admits_indexed_torrent(monkeypatch):
    monkeypatch.setattr(
        catalog_menus, "current_stremio_playback_capabilities", lambda: {"youtube_available": True}
    )

    playback_data, candidate = catalog_menus._stremio_catalog_playback_data(
        _supported_hash_payload(fileIdx=3), _catalog_params()
    )

    assert candidate.fileIdx == 3
    assert playback_data["file_idx"] == 3
    assert playback_data["is_torrent"] is True


@pytest.mark.parametrize(
    ("metadata_key", "metadata", "admitted"),
    [
        pytest.param("stremio_metadata", json.dumps({"fileIdx": 3}), True, id="snake_valid_index"),
        pytest.param("stremioMetadata", json.dumps({"fileIdx": 3}), True, id="camel_valid_index"),
        pytest.param("stremio_metadata", '{"fileIdx": 3', False, id="snake_malformed"),
        pytest.param("stremioMetadata", '{"fileIdx": 3', False, id="camel_malformed"),
        pytest.param(
            "stremio_metadata",
            json.dumps({"fileIdx": 3, "debridType": DebridType.RD}),
            True,
            id="snake_debrid_intent",
        ),
        pytest.param(
            "stremioMetadata",
            json.dumps({"fileIdx": 3, "debridType": DebridType.RD}),
            True,
            id="camel_debrid_intent",
        ),
    ],
)
def test_catalog_normalizes_serialized_stremio_metadata_before_admission(
    monkeypatch, metadata_key, metadata, admitted
):
    monkeypatch.setattr(
        catalog_menus, "current_stremio_playback_capabilities", lambda: {"youtube_available": True}
    )

    prepared = catalog_menus._stremio_catalog_playback_data(
        _supported_hash_payload(**{metadata_key: metadata}), _catalog_params()
    )

    assert (prepared is not None) is admitted
    if admitted:
        assert prepared[0]["file_idx"] == 3


@pytest.mark.parametrize(
    "stream",
    [
        pytest.param({"url": "https://media.example/movie.mkv", "fileIdx": 3}, id="direct"),
        pytest.param({"ytId": "dQw4w9WgXcQ", "fileIdx": 3}, id="youtube"),
    ],
)
def test_catalog_rejects_bare_indexed_non_torrent_sources_without_jacktorr(monkeypatch, stream):
    monkeypatch.setattr(
        catalog_menus,
        "current_stremio_playback_capabilities",
        lambda: {"youtube_available": True},
    )

    assert catalog_menus._stremio_catalog_playback_data(stream, _catalog_params()) is None


def test_catalog_admits_hidden_debrid_intent_in_second_metadata_alias(monkeypatch):
    monkeypatch.setattr(
        catalog_menus,
        "current_stremio_playback_capabilities",
        lambda: {"youtube_available": True},
    )
    stream = _supported_hash_payload(
        fileIdx=3,
        stremioMetadata={"title": "Benign metadata"},
        stremio_metadata={"debridType": DebridType.RD},
    )

    assert catalog_menus._stremio_catalog_playback_data(stream, _catalog_params()) is not None


@pytest.mark.parametrize("debrid_type", DebridType.values())
def test_catalog_admits_indexed_torrent_debrid_routes(monkeypatch, debrid_type):
    monkeypatch.setattr(
        catalog_menus, "current_stremio_playback_capabilities", lambda: {"youtube_available": True}
    )

    prepared = catalog_menus._stremio_catalog_playback_data(
        _supported_hash_payload(fileIdx=3, debrid_type=debrid_type), _catalog_params()
    )

    assert prepared is not None


def test_catalog_serialized_indexed_torrent_uses_normal_playback_resolution(monkeypatch):
    monkeypatch.setattr(
        catalog_menus,
        "current_stremio_playback_capabilities",
        lambda: {"youtube_available": True},
    )
    playback_data, _candidate = catalog_menus._stremio_catalog_playback_data(
        _supported_hash_payload(fileIdx=3), _catalog_params()
    )
    player = MagicMock()
    notifications = []

    monkeypatch.setattr(
        player_utils,
        "resolve_playback_url",
        lambda data: {**data, "url": "plugin://normal/play"},
    )
    monkeypatch.setattr(navigation, "JacktookPLayer", lambda: player)
    monkeypatch.setattr(navigation, "notification", notifications.append)

    navigation.play_media({"data": json.dumps(playback_data)})

    player.run.assert_called_once()
    assert notifications == []


def test_catalog_serialized_indexed_torrent_does_not_pass_index_to_jacktorr(monkeypatch):
    settings = {"torrent_enable": True, "torrent_client": Players.JACKTORR}
    monkeypatch.setattr(
        catalog_menus, "current_stremio_playback_capabilities", lambda: {"youtube_available": True}
    )
    playback_data, _candidate = catalog_menus._stremio_catalog_playback_data(
        _supported_hash_payload(fileIdx=0), _catalog_params()
    )
    player = MagicMock()
    selector_calls = []

    monkeypatch.setattr(player_utils, "get_setting", lambda setting: settings.get(setting))
    monkeypatch.setattr(
        player_utils,
        "get_jacktorr_url",
        lambda magnet, url, data=None: selector_calls.append((magnet, url, data))
        or "plugin://plugin.video.jacktorr/play_magnet",
    )
    monkeypatch.setattr(navigation, "JacktookPLayer", lambda: player)

    navigation.play_media({"data": json.dumps(playback_data)})

    assert "file_idx" not in selector_calls[0][2]
    assert "fileIdx" not in selector_calls[0][2]
    player.run.assert_called_once_with(
        data={**playback_data, "url": "plugin://plugin.video.jacktorr/play_magnet"}
    )


@pytest.mark.parametrize("entry_point", [navigation.play_media, navigation.play_from_pack])
def test_runtime_routes_delegate_clean_unindexed_payloads_to_legacy_resolution(monkeypatch, entry_point):
    payload = {"url": "https://media.example/movie.mkv", "title": "Clean stream"}
    player = MagicMock()
    legacy_calls = []

    monkeypatch.setattr(
        player_utils,
        "resolve_playback_url",
        lambda data: legacy_calls.append(data) or {**data, "url": "plugin://legacy/play"},
    )
    monkeypatch.setattr(navigation, "JacktookPLayer", lambda: player)

    entry_point({"data": json.dumps(payload)})

    assert legacy_calls == [payload]


def test_file_index_zero_reaches_legacy_resolution(monkeypatch):
    payload = _supported_hash_payload(fileIdx=0)
    selector_calls = []
    legacy_calls = []

    monkeypatch.setattr(
        player_utils,
        "get_torrent_url",
        lambda data, client: selector_calls.append((data, client)) or "plugin://jacktorr/selector",
    )
    monkeypatch.setattr(
        player_utils, "resolve_playback_url", lambda data: legacy_calls.append(data) or data
    )

    resolved = stremio_playback.resolve_stremio_playback_url(payload)

    assert resolved["file_idx"] == 0
    assert selector_calls == []
    assert legacy_calls[0]["file_idx"] == 0


@pytest.mark.parametrize("destination", ["debrid", "torrest", "elementum"])
def test_serialized_file_index_uses_existing_route_without_index_handoff(monkeypatch, destination):
    data = {
        "info_hash": INFO_HASH,
        "magnet": f"magnet:?xt=urn:btih:{INFO_HASH}",
        "stremio_metadata": json.dumps({"file_idx": 3}),
    }
    resolver_calls = []
    if destination == "debrid":
        data["debrid_type"] = DebridType.RD
        monkeypatch.setattr(
            player_utils,
            "get_debrid_url",
            lambda payload, debrid_type, is_pack: resolver_calls.append(
                (payload, debrid_type, is_pack)
            )
            or "https://media.example/debrid",
        )
    elif destination == "torrest":
        monkeypatch.setattr(player_utils, "get_setting", lambda setting: True if setting == "torrent_enable" else Players.TORREST)
        monkeypatch.setattr(
            player_utils,
            "get_torrest_url",
            lambda magnet, url: resolver_calls.append((magnet, url)) or "plugin://torrest/play",
        )
    else:
        monkeypatch.setattr(player_utils, "get_setting", lambda setting: True if setting == "torrent_enable" else Players.ELEMENTUM)
        monkeypatch.setattr(
            player_utils,
            "get_elementum_url",
            lambda magnet, url, mode, ids: resolver_calls.append((magnet, url, mode, ids)) or "plugin://elementum/play",
        )

    resolved = stremio_playback.resolve_stremio_playback_url(data)

    assert resolver_calls
    assert resolved["file_idx"] == 3


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(
            {"type": IndexerType.DIRECT, "url": "https://media.example/movie.mkv", "fileIdx": 3},
            id="direct_http",
        ),
        pytest.param({"ytId": "dQw4w9WgXcQ", "fileIdx": 3}, id="youtube"),
    ],
)
def test_indexed_non_torrent_sources_reject_with_fresh_jacktorr_before_resolution(
    monkeypatch, data
):
    monkeypatch.setattr(stremio_playback, "is_youtube_addon_enabled", lambda: True)

    _assert_stremio_runtime_rejected_before_resolution(monkeypatch, data)


@pytest.mark.parametrize("metadata_key", ["stremio_metadata", "stremioMetadata"])
def test_unindexed_serialized_metadata_preserves_direct_torrent_and_debrid_resolution(
    monkeypatch, metadata_key
):
    direct = {"type": IndexerType.DIRECT, "url": "https://media.example/direct", metadata_key: "{}"}
    torrent = {"url": "magnet:?xt=urn:btih:example", metadata_key: "{}"}
    debrid = {"debrid_type": DebridType.RD, "url": "https://media.example/debrid", metadata_key: "{}"}
    torrent_resolver = MagicMock(return_value="plugin://torrent/play")
    debrid_resolver = MagicMock(return_value="https://media.example/resolved")
    monkeypatch.setattr(player_utils, "get_torrent_url", torrent_resolver)
    monkeypatch.setattr(player_utils, "get_debrid_url", debrid_resolver)

    assert player_utils.resolve_playback_url(direct) is direct
    assert player_utils.resolve_playback_url(torrent)["url"] == "plugin://torrent/play"
    assert player_utils.resolve_playback_url(debrid) is debrid
    torrent_resolver.assert_called_once_with(torrent)
    debrid_resolver.assert_called_once_with(debrid, DebridType.RD, False)


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


def test_channel_streams_reuse_tv_playback_and_close_on_incomplete_data(monkeypatch):
    captured = []
    closed = []
    monkeypatch.setattr(catalog_menus, "make_list_item", lambda label="": MagicMock())
    monkeypatch.setattr(catalog_menus, "end_of_directory", lambda *args: closed.append(True))
    monkeypatch.setattr(catalog_menus, "notification", lambda *args: None)
    monkeypatch.setattr(catalog_menus, "build_url", lambda action, **kwargs: kwargs["data"])
    monkeypatch.setattr(catalog_menus, "add_directory_items_batch", captured.extend)
    monkeypatch.setattr(catalog_menus, "catalogs_get_cache", lambda *args: {"streams": []})

    catalog_menus.list_stremio_tv(_catalog_params(catalog_type="channel"))
    catalog_menus.list_stremio_tv_streams(
        _catalog_params(
            catalog_type="channel",
            streams=json.dumps([{"url": "https://example.com/news.m3u8"}, {"name": "Missing"}]),
        )
    )

    assert closed == [True, True]
    assert json.loads(captured[0][0])["url"] == "https://example.com/news.m3u8"
    assert json.loads(captured[0][0])["type"] == catalog_menus.IndexerType.DIRECT


def test_channel_streams_mark_fetched_and_embedded_payloads_as_live_tv(monkeypatch):
    fetched = _capture_catalog_builder(
        monkeypatch,
        catalog_menus.list_stremio_tv,
        {"streams": [{"url": "https://example.com/fetched-news.m3u8"}]},
        _catalog_params(catalog_type="channel"),
    )
    captured = []
    monkeypatch.setattr(catalog_menus, "end_of_directory", lambda *args: None)
    monkeypatch.setattr(catalog_menus, "make_list_item", lambda label="": MagicMock())
    monkeypatch.setattr(catalog_menus, "add_directory_items_batch", captured.extend)
    monkeypatch.setattr(catalog_menus, "build_url", lambda action, **kwargs: kwargs["data"])

    catalog_menus.list_stremio_tv_streams(
        _catalog_params(
            catalog_type="channel",
            streams=json.dumps([{"url": "https://example.com/embedded-news.m3u8"}]),
        )
    )

    assert fetched[0]["is_live_tv"] is True
    assert json.loads(captured[0][0])["is_live_tv"] is True


def test_catalog_no_stream_placeholder_marks_payload_as_informational():
    playback_data, _candidate = catalog_menus._stremio_catalog_playback_data(
        {"url": "https://streamvix.example/nostream.mp4", "title": "Nessuno Stream"},
        _catalog_params(
            catalog_type="tv",
            meta_id="tv:placeholder-movies",
            ids=json.dumps({"original_id": "tv:placeholder-movies"}),
        ),
    )

    assert playback_data["is_informational_placeholder"] is True
    assert "is_live_tv" not in playback_data


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


def _catalog_client():
    return addon_client.StremioAddonCatalogsClient(
        {
            "addon_url": "https://private.addon.example/token",
            "catalog_type": "movie",
            "catalog_id": "secret-catalog-id",
        }
    )


def _assert_safe_catalog_logs(logs):
    log_output = "\n".join(call.args[0] for call in logs.call_args_list)
    assert "private.addon.example" not in log_output
    assert "token" not in log_output
    assert "secret-catalog-id" not in log_output
    assert "Sensitive Search" not in log_output
    assert "Private Genre" not in log_output
    return log_output


def test_catalog_telemetry_logs_safe_success_details(monkeypatch):
    client = _catalog_client()
    kodilog = MagicMock()

    class _Response:
        status_code = 200

        def json(self):
            return {"metas": [{"id": "private-meta-id"}, {"id": "another-private-id"}]}

    monkeypatch.setattr(client.session, "get", lambda *args, **kwargs: _Response())
    monkeypatch.setattr(addon_client, "get_int_setting", lambda _key: 7)
    monkeypatch.setattr(addon_client, "kodilog", kodilog)

    client.get_catalog_info(search="Sensitive Search", genre="Private Genre")

    log_output = _assert_safe_catalog_logs(kodilog)
    assert "catalog_type=movie" in log_output
    assert "extra_keys=['genre', 'search']" in log_output
    assert "http_status=200" in log_output
    assert "metas=2" in log_output


def test_catalog_telemetry_logs_safe_http_error(monkeypatch):
    client = _catalog_client()
    kodilog = MagicMock()

    class _Response:
        status_code = 503

    monkeypatch.setattr(client.session, "get", lambda *args, **kwargs: _Response())
    monkeypatch.setattr(addon_client, "get_int_setting", lambda _key: 7)
    monkeypatch.setattr(addon_client, "kodilog", kodilog)

    assert client.get_catalog_info(search="Sensitive Search") is None

    log_output = _assert_safe_catalog_logs(kodilog)
    assert "http_status=503" in log_output
    assert "failure=http_error" in log_output


def test_catalog_telemetry_logs_safe_invalid_json(monkeypatch):
    client = _catalog_client()
    kodilog = MagicMock()

    class _Response:
        status_code = 200

        def json(self):
            raise ValueError("https://private.addon.example/token")

    monkeypatch.setattr(client.session, "get", lambda *args, **kwargs: _Response())
    monkeypatch.setattr(addon_client, "get_int_setting", lambda _key: 7)
    monkeypatch.setattr(addon_client, "kodilog", kodilog)

    with pytest.raises(ValueError):
        client.get_catalog_info(search="Sensitive Search")

    log_output = _assert_safe_catalog_logs(kodilog)
    assert "http_status=200" in log_output
    assert "failure=invalid_json" in log_output


def test_catalog_telemetry_logs_safe_request_error(monkeypatch):
    client = _catalog_client()
    kodilog = MagicMock()

    def _raise_request_error(*args, **kwargs):
        raise RuntimeError("https://private.addon.example/token")

    monkeypatch.setattr(client.session, "get", _raise_request_error)
    monkeypatch.setattr(addon_client, "get_int_setting", lambda _key: 7)
    monkeypatch.setattr(addon_client, "kodilog", kodilog)

    with pytest.raises(RuntimeError):
        client.get_catalog_info(search="Sensitive Search")

    log_output = _assert_safe_catalog_logs(kodilog)
    assert "http_status=unavailable" in log_output
    assert "failure=request_error" in log_output


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
