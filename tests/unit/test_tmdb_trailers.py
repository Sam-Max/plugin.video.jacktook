import os
from unittest.mock import patch

from lib.api.tmdbv3api.as_obj import AsObj
from lib.clients.tmdb.trailers import (
    _normalize_media_type,
    choose_tmdb_trailer,
    resolve_tmdb_trailer,
)


def test_normalize_media_type_supports_movie_and_tv_variants():
    assert _normalize_media_type("movie") == "movie"
    assert _normalize_media_type("movies") == "movie"
    assert _normalize_media_type("tv") == "tv"
    assert _normalize_media_type("shows") == "tv"


def test_normalize_media_type_returns_none_for_unsupported_values():
    assert _normalize_media_type(None) is None
    assert _normalize_media_type("documentary") is None


def test_choose_tmdb_trailer_prefers_trailer_over_teaser_then_official_flag():
    videos = [
        {
            "site": "YouTube",
            "type": "Teaser",
            "official": True,
            "key": "teaser12345A",
        },
        {
            "site": "YouTube",
            "type": "Trailer",
            "official": False,
            "key": "trailer1234",
        },
        {
            "site": "YouTube",
            "type": "Trailer",
            "official": True,
            "key": "official1234",
        },
    ]

    assert choose_tmdb_trailer(videos) == {
        "yt_id": "official1234",
        "youtube_url": "https://www.youtube.com/watch?v=official1234",
    }


def test_choose_tmdb_trailer_ignores_non_youtube_and_unrelated_types():
    videos = [
        {"site": "Vimeo", "type": "Trailer", "official": True, "key": "vimeo123456"},
        {"site": "YouTube", "type": "Behind the Scenes", "official": True, "key": "bts12345678"},
    ]

    assert choose_tmdb_trailer(videos) is None


def test_choose_tmdb_trailer_accepts_clip_as_lower_priority_fallback():
    videos = [
        {"site": "YouTube", "type": "Clip", "official": True, "key": "clip1234567"},
        {"site": "YouTube", "type": "Teaser", "official": False, "key": "teaser12345"},
    ]

    assert choose_tmdb_trailer(videos) == {
        "yt_id": "teaser12345",
        "youtube_url": "https://www.youtube.com/watch?v=teaser12345",
    }


def test_choose_tmdb_trailer_uses_clip_when_no_trailer_or_teaser_exists():
    videos = [
        {"site": "YouTube", "type": "Clip", "official": True, "key": "clip1234567"},
    ]

    assert choose_tmdb_trailer(videos) == {
        "yt_id": "clip1234567",
        "youtube_url": "https://www.youtube.com/watch?v=clip1234567",
    }


def test_resolve_tmdb_trailer_uses_movie_wrapper(monkeypatch):
    class FakeMovie:
        def videos(self, tmdb_id, page=1):
            assert tmdb_id == 550
            assert page == 1
            return [
                {
                    "site": "YouTube",
                    "type": "Trailer",
                    "official": True,
                    "key": "movie123456",
                }
            ]

    monkeypatch.setattr("lib.clients.tmdb.trailers.Movie", FakeMovie)

    assert resolve_tmdb_trailer(550, "movies") == {
        "yt_id": "movie123456",
        "youtube_url": "https://www.youtube.com/watch?v=movie123456",
    }


def test_resolve_tmdb_trailer_uses_tv_wrapper(monkeypatch):
    class FakeTV:
        def videos(self, tmdb_id, include_video_language=None, page=1):
            assert tmdb_id == 1399
            assert include_video_language is None
            assert page == 1
            return [
                {
                    "site": "YouTube",
                    "type": "Teaser",
                    "official": False,
                    "key": "tv123456789",
                }
            ]

    monkeypatch.setattr("lib.clients.tmdb.trailers.TV", FakeTV)

    assert resolve_tmdb_trailer(1399, "tv") == {
        "yt_id": "tv123456789",
        "youtube_url": "https://www.youtube.com/watch?v=tv123456789",
    }


def test_resolve_tmdb_trailer_handles_tv_wrapper_results_dict(monkeypatch):
    class FakeTV:
        def videos(self, tmdb_id, include_video_language=None, page=1):
            assert tmdb_id == 1416
            return {
                "id": tmdb_id,
                "results": [
                    {
                        "site": "YouTube",
                        "type": "Trailer",
                        "official": True,
                        "key": "tvresults01",
                    }
                ],
            }

    monkeypatch.setattr("lib.clients.tmdb.trailers.TV", FakeTV)

    assert resolve_tmdb_trailer(1416, "tv") == {
        "yt_id": "tvresults01",
        "youtube_url": "https://www.youtube.com/watch?v=tvresults01",
    }


def test_resolve_tmdb_trailer_handles_tv_wrapper_asobj_with_results(monkeypatch):
    class FakeTV:
        def videos(self, tmdb_id, include_video_language=None, page=1):
            return AsObj(
                {
                    "id": tmdb_id,
                    "results": [
                        {
                            "site": "YouTube",
                            "type": "Trailer",
                            "official": True,
                            "key": "tvasobj001",
                        }
                    ],
                }
            )

    monkeypatch.setattr("lib.clients.tmdb.trailers.TV", FakeTV)

    assert resolve_tmdb_trailer(1622, "tv") == {
        "yt_id": "tvasobj001",
        "youtube_url": "https://www.youtube.com/watch?v=tvasobj001",
    }


def test_resolve_tmdb_trailer_returns_none_for_invalid_media_type():
    assert resolve_tmdb_trailer(1, "person") is None


def test_resolve_tmdb_trailer_logs_when_no_candidate_found(monkeypatch):
    class FakeMovie:
        def videos(self, tmdb_id, page=1):
            return []

    monkeypatch.setattr("lib.clients.tmdb.trailers.Movie", FakeMovie)

    with patch("lib.clients.tmdb.trailers.kodilog") as log_mock:
        assert resolve_tmdb_trailer(550, "movie") is None

    log_mock.assert_called()


def test_resolve_tmdb_trailer_retries_tv_lookup_with_language_fallback(monkeypatch):
    calls = []

    class FakeTV:
        def __init__(self):
            self.language = None

        def videos(self, tmdb_id, include_video_language=None, page=1):
            calls.append((self.language, include_video_language))
            if len(calls) == 1:
                return []
            return [
                {
                    "site": "YouTube",
                    "type": "Trailer",
                    "official": True,
                    "key": "fallbacktv01",
                }
            ]

    monkeypatch.setattr("lib.clients.tmdb.trailers.TV", FakeTV)
    monkeypatch.setenv("TMDB_LANGUAGE", "es-ES")

    assert resolve_tmdb_trailer(4604, "tv") == {
        "yt_id": "fallbacktv01",
        "youtube_url": "https://www.youtube.com/watch?v=fallbacktv01",
    }
    assert calls == [
        ("es-ES", "es-ES,null"),
        ("en-US", "en-US,null"),
    ]


def test_resolve_tmdb_trailer_retries_movie_lookup_with_language_fallback(monkeypatch):
    calls = []

    class FakeMovie:
        def __init__(self):
            self.language = None

        def videos(self, tmdb_id, page=1):
            calls.append(self.language)
            if len(calls) == 1:
                return []
            return [
                {
                    "site": "YouTube",
                    "type": "Clip",
                    "official": False,
                    "key": "fallbackmv1",
                }
            ]

    monkeypatch.setattr("lib.clients.tmdb.trailers.Movie", FakeMovie)
    monkeypatch.setenv("TMDB_LANGUAGE", "fr-FR")

    assert resolve_tmdb_trailer(550, "movie") == {
        "yt_id": "fallbackmv1",
        "youtube_url": "https://www.youtube.com/watch?v=fallbackmv1",
    }
    assert calls == ["fr-FR", "en-US"]
