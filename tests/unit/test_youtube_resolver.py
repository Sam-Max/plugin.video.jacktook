import pytest
from unittest.mock import MagicMock, patch


from lib.clients.youtube_resolver import (
    extract_video_id,
    parse_watch_config,
    resolve_item_trailer_metadata,
    resolve_item_trailer_playback,
    resolve_trailer_playback,
    select_best_stream,
)


WATCH_HTML = """
<html>
  <script>
    var ytcfg = {
      "INNERTUBE_API_KEY": "test-api-key",
      "VISITOR_DATA": "visitor-token"
    };
  </script>
</html>
"""


class FakeResponse:
    def __init__(self, text="", payload=None, status_code=200):
        self.text = text
        self._payload = payload if payload is not None else {}
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("http error")


class FakeSession:
    def __init__(self, watch_response, player_responses):
        self.watch_response = watch_response
        self.player_responses = list(player_responses)
        self.get_calls = []
        self.post_calls = []

    def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        return self.watch_response

    def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        if not self.player_responses:
            raise AssertionError("unexpected player call")
        return self.player_responses.pop(0)


@pytest.fixture(autouse=True)
def clear_resolver_cache():
    from lib.clients import youtube_resolver

    youtube_resolver._RESOLVER_CACHE.clear()
    yield
    youtube_resolver._RESOLVER_CACHE.clear()


@pytest.mark.parametrize(
    "value",
    [
        "dQw4w9WgXcQ",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://www.youtube.com/embed/dQw4w9WgXcQ",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ",
        "https://www.youtube.com/live/dQw4w9WgXcQ",
    ],
)
def test_extract_video_id_supports_common_youtube_inputs(value):
    assert extract_video_id(value) == "dQw4w9WgXcQ"


def test_extract_video_id_rejects_unknown_values():
    assert extract_video_id("https://example.com/watch?v=invalid") is None


def test_parse_watch_config_extracts_api_key_and_visitor_data():
    assert parse_watch_config(WATCH_HTML) == {
        "api_key": "test-api-key",
        "visitor_data": "visitor-token",
    }


def test_parse_watch_config_requires_api_key():
    assert parse_watch_config("<html>missing config</html>") is None


def test_select_best_stream_returns_hls_manifest_url_as_last_resort():
    payload = {
        "streamingData": {
            "hlsManifestUrl": "https://video.example/hls.m3u8",
        }
    }

    assert select_best_stream(payload) == {
        "video_url": "https://video.example/hls.m3u8",
        "audio_url": None,
        "source_type": "hls",
    }


def test_select_best_stream_prefers_adaptive_pair_over_hls_for_max_quality():
    payload = {
        "streamingData": {
            "hlsManifestUrl": "https://video.example/master.m3u8",
            "adaptiveFormats": [
                {
                    "url": "https://video.example/video-1080.mp4",
                    "mimeType": 'video/mp4; codecs="avc1"',
                    "height": 1080,
                    "fps": 30,
                    "bitrate": 4000000,
                },
                {
                    "url": "https://video.example/audio-160.m4a",
                    "mimeType": 'audio/mp4; codecs="mp4a"',
                    "bitrate": 160000,
                    "audioSampleRate": "48000",
                },
            ],
        }
    }

    assert select_best_stream(payload) == {
        "video_url": "https://video.example/video-1080.mp4",
        "audio_url": "https://video.example/audio-160.m4a",
        "source_type": "adaptive",
    }


def test_select_best_stream_prefers_mp4_adaptive_video_over_similar_webm_when_quality_close():
    payload = {
        "streamingData": {
            "adaptiveFormats": [
                {
                    "url": "https://video.example/video-1080.webm",
                    "mimeType": 'video/webm; codecs="vp9"',
                    "height": 1080,
                    "fps": 30,
                    "bitrate": 4050000,
                },
                {
                    "url": "https://video.example/video-1080.mp4",
                    "mimeType": 'video/mp4; codecs="avc1"',
                    "height": 1080,
                    "fps": 30,
                    "bitrate": 4000000,
                },
                {
                    "url": "https://video.example/audio-160.m4a",
                    "mimeType": 'audio/mp4; codecs="mp4a"',
                    "bitrate": 160000,
                    "audioSampleRate": "48000",
                },
            ],
        }
    }

    result = select_best_stream(payload)

    assert result["video_url"] == "https://video.example/video-1080.mp4"
    assert result["source_type"] == "adaptive"


def test_select_best_stream_prefers_materially_better_webm_over_mp4():
    payload = {
        "streamingData": {
            "adaptiveFormats": [
                {
                    "url": "https://video.example/video-1080.webm",
                    "mimeType": 'video/webm; codecs="vp9"',
                    "height": 1080,
                    "fps": 30,
                    "bitrate": 5200000,
                },
                {
                    "url": "https://video.example/video-1080.mp4",
                    "mimeType": 'video/mp4; codecs="avc1"',
                    "height": 1080,
                    "fps": 30,
                    "bitrate": 4000000,
                },
                {
                    "url": "https://video.example/audio-160.m4a",
                    "mimeType": 'audio/mp4; codecs="mp4a"',
                    "bitrate": 160000,
                    "audioSampleRate": "48000",
                },
            ],
        }
    }

    result = select_best_stream(payload)

    assert result["video_url"] == "https://video.example/video-1080.webm"
    assert result["source_type"] == "adaptive"


def test_select_best_stream_uses_highest_progressive_format_when_hls_missing():
    payload = {
        "streamingData": {
            "formats": [
                {
                    "url": "https://video.example/360.mp4",
                    "mimeType": 'video/mp4; codecs="avc1"',
                    "height": 360,
                },
                {
                    "url": "https://video.example/720.mp4",
                    "mimeType": 'video/mp4; codecs="avc1, mp4a"',
                    "qualityLabel": "720p",
                    "height": 720,
                },
            ]
        }
    }

    assert select_best_stream(payload) == {
        "video_url": "https://video.example/720.mp4",
        "audio_url": None,
        "source_type": "progressive",
    }


def test_select_best_stream_prefers_progressive_when_no_hls_and_no_adaptive_pair():
    payload = {
        "streamingData": {
            "formats": [
                {
                    "url": "https://video.example/720.mp4",
                    "mimeType": 'video/mp4; codecs="avc1, mp4a"',
                    "height": 720,
                    "bitrate": 2000000,
                }
            ],
            "adaptiveFormats": [
                {
                    "url": "https://video.example/video-only.webm",
                    "mimeType": 'video/webm; codecs="vp9"',
                    "height": 1080,
                    "bitrate": 3000000,
                }
            ],
        }
    }

    assert select_best_stream(payload) == {
        "video_url": "https://video.example/720.mp4",
        "audio_url": None,
        "source_type": "progressive",
    }


def test_select_best_stream_returns_adaptive_video_and_audio_pair_when_needed():
    payload = {
        "streamingData": {
            "formats": [],
            "adaptiveFormats": [
                {
                    "url": "https://video.example/video-only.mp4",
                    "mimeType": 'video/mp4; codecs="avc1"',
                    "height": 1080,
                    "bitrate": 3000000,
                },
                {
                    "url": "https://video.example/audio-only.m4a",
                    "mimeType": 'audio/mp4; codecs="mp4a"',
                    "bitrate": 128000,
                    "audioSampleRate": "48000",
                },
            ],
        }
    }

    assert select_best_stream(payload) == {
        "video_url": "https://video.example/video-only.mp4",
        "audio_url": "https://video.example/audio-only.m4a",
        "source_type": "adaptive",
    }


def test_select_best_stream_uses_scoring_to_pick_best_adaptive_video_and_audio():
    payload = {
        "streamingData": {
            "formats": [],
            "adaptiveFormats": [
                {
                    "url": "https://video.example/video-720.mp4",
                    "mimeType": 'video/mp4; codecs="avc1"',
                    "height": 720,
                    "fps": 30,
                    "bitrate": 2000000,
                },
                {
                    "url": "https://video.example/video-1080-lowfps.mp4",
                    "mimeType": 'video/mp4; codecs="avc1"',
                    "height": 1080,
                    "fps": 24,
                    "bitrate": 2500000,
                },
                {
                    "url": "https://video.example/audio-128.m4a",
                    "mimeType": 'audio/mp4; codecs="mp4a"',
                    "bitrate": 128000,
                    "audioSampleRate": "44100",
                },
                {
                    "url": "https://video.example/audio-160.m4a",
                    "mimeType": 'audio/mp4; codecs="mp4a"',
                    "bitrate": 160000,
                    "audioSampleRate": "48000",
                },
            ],
        }
    }

    assert select_best_stream(payload) == {
        "video_url": "https://video.example/video-1080-lowfps.mp4",
        "audio_url": "https://video.example/audio-160.m4a",
        "source_type": "adaptive",
    }


def test_resolve_trailer_playback_fetches_watch_page_then_player_api_and_caches_result():
    first_player_payload = {
        "playabilityStatus": {"status": "ERROR"},
    }
    second_player_payload = {
        "playabilityStatus": {"status": "OK"},
        "streamingData": {
            "hlsManifestUrl": "https://video.example/master.m3u8",
        },
    }
    session = FakeSession(
        watch_response=FakeResponse(text=WATCH_HTML),
        player_responses=[
            FakeResponse(payload=first_player_payload),
            FakeResponse(payload=second_player_payload),
        ],
    )

    resolved = resolve_trailer_playback(
        "https://youtu.be/dQw4w9WgXcQ",
        session=session,
    )

    assert resolved == {
        "video_url": "https://video.example/master.m3u8",
        "audio_url": None,
        "source_type": "hls",
        "video_id": "dQw4w9WgXcQ",
    }
    assert len(session.get_calls) == 1
    assert len(session.post_calls) == 2
    first_post_url, first_post_kwargs = session.post_calls[0]
    assert first_post_url == "https://www.youtube.com/youtubei/v1/player"
    assert first_post_kwargs["params"] == {"key": "test-api-key"}
    assert first_post_kwargs["headers"]["X-Goog-Visitor-Id"] == "visitor-token"
    assert first_post_kwargs["json"]["videoId"] == "dQw4w9WgXcQ"

    cached = resolve_trailer_playback("dQw4w9WgXcQ", session=session)
    assert cached == resolved
    assert len(session.get_calls) == 1
    assert len(session.post_calls) == 2


def test_resolve_trailer_playback_skips_unplayable_stream_payloads():
    session = FakeSession(
        watch_response=FakeResponse(text=WATCH_HTML),
        player_responses=[
            FakeResponse(
                payload={
                    "playabilityStatus": {"status": "ERROR"},
                    "streamingData": {
                        "hlsManifestUrl": "https://video.example/blocked.m3u8",
                    },
                }
            ),
            FakeResponse(
                payload={
                    "playabilityStatus": {"status": "OK"},
                    "streamingData": {
                        "hlsManifestUrl": "https://video.example/playable.m3u8",
                    },
                }
            ),
        ],
    )

    assert resolve_trailer_playback("dQw4w9WgXcQ", session=session) == {
        "video_url": "https://video.example/playable.m3u8",
        "audio_url": None,
        "source_type": "hls",
        "video_id": "dQw4w9WgXcQ",
    }


def test_resolve_trailer_playback_accepts_named_youtube_url_argument():
    session = FakeSession(
        watch_response=FakeResponse(text=WATCH_HTML),
        player_responses=[
            FakeResponse(
                payload={
                    "playabilityStatus": {"status": "OK"},
                    "streamingData": {
                        "hlsManifestUrl": "https://video.example/named-input.m3u8",
                    },
                }
            )
        ],
    )

    assert resolve_trailer_playback(
        youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        session=session,
    ) == {
        "video_url": "https://video.example/named-input.m3u8",
        "audio_url": None,
        "source_type": "hls",
        "video_id": "dQw4w9WgXcQ",
    }


def test_resolve_trailer_playback_tries_android_vr_android_then_ios_clients():
    session = FakeSession(
        watch_response=FakeResponse(text=WATCH_HTML),
        player_responses=[
            FakeResponse(payload={"playabilityStatus": {"status": "ERROR"}}),
            FakeResponse(payload={"playabilityStatus": {"status": "ERROR"}}),
            FakeResponse(
                payload={
                    "playabilityStatus": {"status": "OK"},
                    "streamingData": {
                        "hlsManifestUrl": "https://video.example/final.m3u8",
                    },
                }
            ),
        ],
    )

    resolved = resolve_trailer_playback("dQw4w9WgXcQ", session=session)

    assert resolved["video_url"] == "https://video.example/final.m3u8"
    assert [
        call[1]["json"]["context"]["client"]["clientName"]
        for call in session.post_calls
    ] == ["ANDROID_VR", "ANDROID", "IOS"]
    assert [call[1]["headers"]["User-Agent"] for call in session.post_calls] == [
        (
            "com.google.android.apps.youtube.vr.oculus/1.56.21 "
            "(Linux; U; Android 12; en_US; Quest 3; Build/SQ3A.220605.009.A1) gzip"
        ),
        "com.google.android.youtube/20.10.35 (Linux; U; Android 14; en_US) gzip",
        "com.google.ios.youtube/20.10.1 (iPhone16,2; U; CPU iOS 17_4 like Mac OS X)",
    ]
    assert [call[1]["headers"]["X-YouTube-Client-Name"] for call in session.post_calls] == [
        "28",
        "3",
        "5",
    ]
    assert [
        call[1]["headers"]["X-YouTube-Client-Version"] for call in session.post_calls
    ] == ["1.56.21", "20.10.35", "20.10.1"]
    assert [call[1]["headers"]["X-Goog-Visitor-Id"] for call in session.post_calls] == [
        "visitor-token",
        "visitor-token",
        "visitor-token",
    ]
    assert [call[1]["headers"]["Origin"] for call in session.post_calls] == [
        "https://www.youtube.com",
        "https://www.youtube.com",
        "https://www.youtube.com",
    ]
    assert [
        call[1]["json"]["playbackContext"]["contentPlaybackContext"]["html5Preference"]
        for call in session.post_calls
    ] == ["HTML5_PREF_WANTS", "HTML5_PREF_WANTS", "HTML5_PREF_WANTS"]


def test_call_player_api_sends_origin_and_html5_preference():
    session = FakeSession(
        watch_response=FakeResponse(text=WATCH_HTML),
        player_responses=[
            FakeResponse(
                payload={
                    "playabilityStatus": {"status": "OK"},
                    "streamingData": {
                        "hlsManifestUrl": "https://video.example/request-shape.m3u8",
                    },
                }
            )
        ],
    )

    resolve_trailer_playback("dQw4w9WgXcQ", session=session)

    _, post_kwargs = session.post_calls[0]
    assert post_kwargs["headers"]["Origin"] == "https://www.youtube.com"
    assert (
        post_kwargs["headers"]["User-Agent"]
        == "com.google.android.apps.youtube.vr.oculus/1.56.21 "
        "(Linux; U; Android 12; en_US; Quest 3; Build/SQ3A.220605.009.A1) gzip"
    )
    assert post_kwargs["headers"]["X-YouTube-Client-Name"] == "28"
    assert post_kwargs["headers"]["X-YouTube-Client-Version"] == "1.56.21"
    assert post_kwargs["headers"]["X-Goog-Visitor-Id"] == "visitor-token"
    assert (
        post_kwargs["json"]["playbackContext"]["contentPlaybackContext"][
            "html5Preference"
        ]
        == "HTML5_PREF_WANTS"
    )


def test_resolve_trailer_playback_returns_none_for_unplayable_video():
    session = FakeSession(
        watch_response=FakeResponse(text=WATCH_HTML),
        player_responses=[
            FakeResponse(payload={"playabilityStatus": {"status": "ERROR"}}),
            FakeResponse(payload={"playabilityStatus": {"status": "LOGIN_REQUIRED"}}),
        ],
    )

    assert resolve_trailer_playback("dQw4w9WgXcQ", session=session) is None


def test_resolve_trailer_playback_logs_player_api_error_details():
    session = FakeSession(
        watch_response=FakeResponse(text=WATCH_HTML),
        player_responses=[
            FakeResponse(
                text='{"error":{"message":"bad client"}}',
                payload={"error": {"message": "bad client"}},
                status_code=400,
            )
        ],
    )

    with patch("lib.clients.youtube_resolver.kodilog") as log_mock:
        assert resolve_trailer_playback("dQw4w9WgXcQ", session=session) is None

    assert any(
        "bad client" in str(call) and "preview=" in str(call)
        for call in log_mock.call_args_list
    )


def test_resolve_item_trailer_playback_prefers_direct_youtube_values(monkeypatch):
    playback_calls = []

    def fake_resolve_trailer_playback(video_id=None, youtube_url=None, session=None, cache_ttl=300):
        playback_calls.append(
            {
                "video_id": video_id,
                "youtube_url": youtube_url,
                "session": session,
                "cache_ttl": cache_ttl,
            }
        )
        return {"video_url": "https://video.example/direct.m3u8"}

    def fail_resolve_tmdb_trailer(*args, **kwargs):
        raise AssertionError("tmdb fallback should not be used")

    monkeypatch.setattr(
        "lib.clients.youtube_resolver.resolve_trailer_playback",
        fake_resolve_trailer_playback,
    )
    monkeypatch.setattr(
        "lib.clients.youtube_resolver.resolve_tmdb_trailer",
        fail_resolve_tmdb_trailer,
    )

    resolved = resolve_item_trailer_playback(
        yt_id="dQw4w9WgXcQ",
        youtube_url="https://www.youtube.com/watch?v=ignored12345A",
        tmdb_id=550,
        media_type="movie",
        session="session-token",
    )

    assert resolved == {"video_url": "https://video.example/direct.m3u8"}
    assert playback_calls == [
        {
            "video_id": "dQw4w9WgXcQ",
            "youtube_url": "https://www.youtube.com/watch?v=ignored12345A",
            "session": "session-token",
            "cache_ttl": 300,
        }
    ]


def test_resolve_item_trailer_playback_falls_back_to_tmdb_trailer(monkeypatch):
    tmdb_calls = []
    playback_calls = []

    def fake_resolve_tmdb_trailer(tmdb_id, media_type):
        tmdb_calls.append((tmdb_id, media_type))
        return {
            "yt_id": "tmdb1234567",
            "youtube_url": "https://www.youtube.com/watch?v=tmdb1234567",
        }

    def fake_resolve_trailer_playback(video_id=None, youtube_url=None, session=None, cache_ttl=300):
        playback_calls.append(
            {
                "video_id": video_id,
                "youtube_url": youtube_url,
                "session": session,
            }
        )
        return {"video_url": "https://video.example/fallback.m3u8"}

    monkeypatch.setattr(
        "lib.clients.youtube_resolver.resolve_tmdb_trailer",
        fake_resolve_tmdb_trailer,
    )
    monkeypatch.setattr(
        "lib.clients.youtube_resolver.resolve_trailer_playback",
        fake_resolve_trailer_playback,
    )

    resolved = resolve_item_trailer_playback(
        tmdb_id=1399,
        media_type="tv",
        session="session-token",
    )

    assert resolved == {"video_url": "https://video.example/fallback.m3u8"}
    assert tmdb_calls == [(1399, "tv")]
    assert playback_calls == [
        {
            "video_id": "tmdb1234567",
            "youtube_url": "https://www.youtube.com/watch?v=tmdb1234567",
            "session": "session-token",
        }
    ]


def test_resolve_item_trailer_playback_returns_none_when_no_direct_or_tmdb_trailer(monkeypatch):
    monkeypatch.setattr(
        "lib.clients.youtube_resolver.resolve_tmdb_trailer",
        lambda tmdb_id, media_type: None,
    )
    monkeypatch.setattr(
        "lib.clients.youtube_resolver.resolve_trailer_playback",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("playback should not be resolved")
        ),
    )

    assert resolve_item_trailer_playback(tmdb_id=42, media_type="movie") is None


def test_resolve_item_trailer_metadata_falls_back_to_tmdb_trailer(monkeypatch):
    tmdb_calls = []

    def fake_resolve_tmdb_trailer(tmdb_id, media_type):
        tmdb_calls.append((tmdb_id, media_type))
        return {
            "yt_id": "tmdb1234567",
            "youtube_url": "https://www.youtube.com/watch?v=tmdb1234567",
        }

    monkeypatch.setattr(
        "lib.clients.youtube_resolver.resolve_tmdb_trailer",
        fake_resolve_tmdb_trailer,
    )

    resolved = resolve_item_trailer_metadata(tmdb_id=1399, media_type="tv")

    assert resolved == {
        "yt_id": "tmdb1234567",
        "youtube_url": "https://www.youtube.com/watch?v=tmdb1234567",
    }
    assert tmdb_calls == [(1399, "tv")]


def test_resolve_trailer_playback_logs_when_watch_request_fails():
    session = MagicMock()
    session.get.side_effect = RuntimeError("boom")

    with patch("lib.clients.youtube_resolver.kodilog") as log_mock:
        assert resolve_trailer_playback(video_id="dQw4w9WgXcQ", session=session) is None

    log_mock.assert_called()
