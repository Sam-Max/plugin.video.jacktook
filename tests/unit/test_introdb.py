"""Offline tests for the IntroDB v3 client.

Every HTTP call is stubbed through a fake ``requests.get`` and the module cache
is replaced with an in-memory double, so nothing here touches the network or
the Kodi property store.
"""

from datetime import timedelta

import pytest
import requests

from lib.clients import introdb

SEGMENTS_URL = "https://api.theintrodb.org/v3/media"

# Real IntroDB payload for Attack on Titan S1E2.
AOT_BODY = {
    "tmdb_id": 1429,
    "type": "tv",
    "season": 1,
    "episode": 2,
    "intro": [{"start_ms": 43407, "end_ms": 136575}],
    "recap": [{"start_ms": 0, "end_ms": 42000}],
    "credits": [{"start_ms": 1345005, "end_ms": 1434975}],
    "preview": [{"start_ms": 1435000, "end_ms": None}],
}


class FakeResponse:
    """Minimal stand-in for a requests response."""

    def __init__(self, status_code=200, body=None, text=""):
        self.status_code = status_code
        self._body = body
        self.text = text

    def json(self):
        if self._body is None:
            raise ValueError("malformed json")
        return self._body


class FakeCache:
    """Minimal stand-in for MemoryCache that records every stored entry."""

    def __init__(self):
        self.store = {}
        self.sets = []

    def get(self, key):
        return self.store.get(key)

    def set(self, key, data, expires=None):
        self.store[key] = data
        self.sets.append((key, data, expires))


class FakeHttp:
    """Records outgoing requests and replays queued responses or exceptions."""

    def __init__(self, monkeypatch):
        self.calls = []
        self.queued = []
        monkeypatch.setattr(introdb.requests, "get", self.get)

    def queue(self, *responses):
        self.queued.extend(responses)

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        if not self.queued:
            raise AssertionError("unexpected HTTP request")
        response = self.queued.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def payload(**segments):
    """Build a response body with the given segment types."""
    body = {"tmdb_id": 1, "type": "tv", "season": 1, "episode": 1}
    body.update(segments)
    return body


@pytest.fixture
def cache(monkeypatch):
    fake = FakeCache()
    monkeypatch.setattr(introdb, "_cache", fake)
    return fake


@pytest.fixture
def http(monkeypatch):
    return FakeHttp(monkeypatch)


# --- identifier precedence -------------------------------------------------


def test_uses_the_v3_endpoint_and_prefers_tmdb_id(http, cache):
    http.queue(FakeResponse(body=payload(intro=[{"start_ms": 1000, "end_ms": 2000}])))

    result = introdb.get_segments({"tmdb_id": 1429, "tvdb_id": 33, "imdb_id": "tt0944947"}, 1, 2)

    assert len(http.calls) == 1
    assert http.calls[0]["url"] == SEGMENTS_URL
    assert http.calls[0]["params"] == {"tmdb_id": 1429, "season": 1, "episode": 2}
    assert http.calls[0]["timeout"] == 5
    assert result["intro"] == {
        "start_ms": 1000,
        "end_ms": 2000,
        "start_sec": 1.0,
        "end_sec": 2.0,
    }


def test_tvdb_id_wins_over_imdb_id(http):
    http.queue(FakeResponse(body=payload(intro=[{"start_ms": 1, "end_ms": 2}])))

    introdb.get_segments({"tvdb_id": 81189, "imdb_id": "tt0944947"}, 1, 2)

    assert http.calls[0]["params"] == {"tvdb_id": 81189, "season": 1, "episode": 2}


def test_imdb_id_is_used_when_no_numeric_id_is_available(http):
    http.queue(FakeResponse(body=payload(intro=[{"start_ms": 1, "end_ms": 2}])))

    introdb.get_segments({"tmdb_id": None, "imdb_id": "tt0944947"}, 1, 2)

    assert http.calls[0]["params"] == {
        "imdb_id": "tt0944947",
        "season": 1,
        "episode": 2,
    }


def test_numeric_string_ids_are_coerced_to_integers(http):
    http.queue(FakeResponse(body=payload(intro=[{"start_ms": 1, "end_ms": 2}])))

    introdb.get_segments({"tmdb_id": "1429"}, "1", "2")

    assert http.calls[0]["params"] == {"tmdb_id": 1429, "season": 1, "episode": 2}


@pytest.mark.parametrize(
    "ids",
    [
        {},
        {"tmdb_id": None},
        {"tmdb_id": 0},
        {"tmdb_id": -1},
        {"tmdb_id": "abc"},
        {"tvdb_id": 0},
        {"tvdb_id": "not-a-number"},
        {"imdb_id": ""},
        {"imdb_id": "1399"},
        {"imdb_id": None},
        {"tmdb_id": "abc", "tvdb_id": "-2", "imdb_id": "1399"},
    ],
)
def test_unusable_ids_never_perform_a_request(http, ids):
    assert introdb.get_segments(ids, 1, 2) is None
    assert http.calls == []


@pytest.mark.parametrize(
    ("season", "episode"),
    [
        (None, 2),
        (1, None),
        (0, 2),
        (1, 0),
        (-1, 2),
        (1, -1),
        ("abc", 2),
        (1, "abc"),
    ],
)
def test_missing_or_invalid_episode_info_never_performs_a_request(http, season, episode):
    assert introdb.get_segments({"tmdb_id": 1429}, season, episode) is None
    assert http.calls == []


# --- best candidate selection ---------------------------------------------


def test_highest_confidence_candidate_wins(http, cache):
    http.queue(
        FakeResponse(
            body=payload(
                intro=[
                    {"start_ms": 10, "end_ms": 20, "confidence": 0.4, "submission_count": 1},
                    {"start_ms": 30, "end_ms": 40, "confidence": 0.9, "submission_count": 1},
                ]
            )
        )
    )

    result = introdb.get_segments({"tmdb_id": 1}, 1, 1)

    assert result["intro"]["start_ms"] == 30
    assert result["intro"]["end_ms"] == 40


def test_submission_count_breaks_a_confidence_tie(http):
    http.queue(
        FakeResponse(
            body=payload(
                intro=[
                    {"start_ms": 10, "end_ms": 20, "confidence": 0.5, "submission_count": 1},
                    {"start_ms": 30, "end_ms": 40, "confidence": 0.5, "submission_count": 50},
                ]
            )
        )
    )

    assert introdb.get_segments({"tmdb_id": 1}, 1, 1)["intro"]["start_ms"] == 30


def test_lower_confidence_loses_despite_many_submissions(http):
    # 0.4 + 100 * 0.001 = 0.5 is still below 0.55 + 0.001.
    http.queue(
        FakeResponse(
            body=payload(
                intro=[
                    {"start_ms": 10, "end_ms": 20, "confidence": 0.4, "submission_count": 100},
                    {"start_ms": 30, "end_ms": 40, "confidence": 0.55, "submission_count": 1},
                ]
            )
        )
    )

    assert introdb.get_segments({"tmdb_id": 1}, 1, 1)["intro"]["start_ms"] == 30


def test_equal_scores_keep_the_first_candidate(http):
    http.queue(
        FakeResponse(
            body=payload(
                intro=[
                    {"start_ms": 10, "end_ms": 20, "confidence": 0.5, "submission_count": 1},
                    {"start_ms": 30, "end_ms": 40, "confidence": 0.5, "submission_count": 1},
                ]
            )
        )
    )

    assert introdb.get_segments({"tmdb_id": 1}, 1, 1)["intro"]["start_ms"] == 10


def test_scoring_fields_default_to_low_confidence_single_submission(http):
    http.queue(
        FakeResponse(
            body=payload(
                intro=[
                    {"start_ms": 10, "end_ms": 20},
                    {"start_ms": 30, "end_ms": 40, "confidence": 0.6},
                ]
            )
        )
    )

    assert introdb.get_segments({"tmdb_id": 1}, 1, 1)["intro"]["start_ms"] == 30


# --- type mapping and candidate validation --------------------------------


def test_credits_are_exposed_as_outro_and_preview_is_ignored(http, cache):
    http.queue(FakeResponse(body=AOT_BODY))

    result = introdb.get_segments({"tmdb_id": 1429}, 1, 2)

    assert sorted(result) == ["intro", "outro", "recap"]
    assert result["intro"]["start_ms"] == 43407
    assert result["recap"] == {
        "start_ms": 0,
        "end_ms": 42000,
        "start_sec": 0.0,
        "end_sec": 42.0,
    }
    assert result["outro"] == {
        "start_ms": 1345005,
        "end_ms": 1434975,
        "start_sec": 1345.005,
        "end_sec": 1434.975,
    }
    assert "preview" not in result


def test_candidates_without_a_valid_range_are_dropped(http):
    http.queue(
        FakeResponse(
            body=payload(
                intro=[
                    {"start_ms": None, "end_ms": 100},
                    {"start_ms": 100, "end_ms": None},
                    {"start_ms": 200, "end_ms": 200},
                    {"start_ms": 300, "end_ms": 250},
                ],
                recap=[{"start_ms": 10, "end_ms": 20}],
            )
        )
    )

    result = introdb.get_segments({"tmdb_id": 1}, 1, 1)

    assert "intro" not in result
    assert result["recap"]["start_ms"] == 10


def test_preview_only_response_is_negatively_cached(http, cache):
    http.queue(FakeResponse(body=payload(preview=[{"start_ms": 10, "end_ms": 20}])))

    assert introdb.get_segments({"tmdb_id": 1}, 1, 1) is None
    assert cache.sets[0][1] == introdb._SENTINEL

    assert introdb.get_segments({"tmdb_id": 1}, 1, 1) is None
    assert len(http.calls) == 1


def test_second_boundaries_are_derived_from_milliseconds(http):
    http.queue(FakeResponse(body=payload(intro=[{"start_ms": 43407, "end_ms": 136575}])))

    segment = introdb.get_segments({"tmdb_id": 1}, 1, 1)["intro"]

    assert segment == {
        "start_ms": 43407,
        "end_ms": 136575,
        "start_sec": 43.407,
        "end_sec": 136.575,
    }
    assert segment["start_sec"] == segment["start_ms"] / 1000.0
    assert segment["end_sec"] == segment["end_ms"] / 1000.0


# --- caching ---------------------------------------------------------------


def test_cache_key_is_scoped_to_the_selected_identifier(http, cache):
    http.queue(FakeResponse(body=payload(intro=[{"start_ms": 1, "end_ms": 2}])))

    introdb.get_segments({"imdb_id": "tt0944947"}, 3, 4)

    assert cache.sets[0][0] == "imdb_id:tt0944947.S3E4"
    assert cache.sets[0][2] == timedelta(hours=24)


def test_cached_segments_avoid_a_second_request(http, cache):
    http.queue(FakeResponse(body=payload(intro=[{"start_ms": 1, "end_ms": 2}])))

    first = introdb.get_segments({"tmdb_id": 1429}, 1, 2)
    second = introdb.get_segments({"tmdb_id": 1429}, 1, 2)

    assert len(http.calls) == 1
    assert second == first


@pytest.mark.parametrize(
    "error_body",
    [
        {"error": "media not found"},
        {"error": "media not found for provided season/episode"},
    ],
)
def test_error_body_is_negatively_cached(http, cache, error_body):
    http.queue(FakeResponse(body=error_body))

    assert introdb.get_segments({"tmdb_id": 1}, 1, 1) is None
    assert cache.sets[0][1] == introdb._SENTINEL

    assert introdb.get_segments({"tmdb_id": 1}, 1, 1) is None
    assert len(http.calls) == 1


def test_404_is_negatively_cached(http, cache):
    http.queue(FakeResponse(status_code=404, text="not found"))

    assert introdb.get_segments({"tmdb_id": 1}, 1, 1) is None
    assert cache.sets[0][1] == introdb._SENTINEL

    assert introdb.get_segments({"tmdb_id": 1}, 1, 1) is None
    assert len(http.calls) == 1


def test_response_without_segments_is_negatively_cached(http, cache):
    http.queue(FakeResponse(body=payload(intro=[], recap=None)))

    assert introdb.get_segments({"tmdb_id": 1}, 1, 1) is None
    assert cache.sets[0][1] == introdb._SENTINEL

    assert introdb.get_segments({"tmdb_id": 1}, 1, 1) is None
    assert len(http.calls) == 1


def test_429_is_not_negatively_cached(http, cache):
    http.queue(FakeResponse(status_code=429, text="slow down"))
    http.queue(FakeResponse(body=payload(intro=[{"start_ms": 1, "end_ms": 2}])))

    assert introdb.get_segments({"tmdb_id": 1}, 1, 1) is None
    assert cache.sets == []

    assert introdb.get_segments({"tmdb_id": 1}, 1, 1)["intro"]["end_ms"] == 2
    assert len(http.calls) == 2


def test_timeout_is_not_negatively_cached(http, cache):
    http.queue(requests.exceptions.Timeout("timed out"))
    http.queue(FakeResponse(body=payload(intro=[{"start_ms": 1, "end_ms": 2}])))

    assert introdb.get_segments({"tmdb_id": 1}, 1, 1) is None
    assert cache.sets == []

    assert introdb.get_segments({"tmdb_id": 1}, 1, 1) is not None
    assert len(http.calls) == 2


def test_request_exception_returns_none(http):
    http.queue(requests.exceptions.ConnectionError("no route to host"))

    assert introdb.get_segments({"tmdb_id": 1}, 1, 1) is None
    assert len(http.calls) == 1


def test_non_200_response_is_not_negatively_cached(http, cache):
    http.queue(FakeResponse(status_code=500, text="boom"))
    http.queue(FakeResponse(body=payload(recap=[{"start_ms": 5, "end_ms": 6}])))

    assert introdb.get_segments({"tmdb_id": 1}, 1, 1) is None
    assert cache.sets == []

    assert introdb.get_segments({"tmdb_id": 1}, 1, 1)["recap"]["start_ms"] == 5
    assert len(http.calls) == 2


def test_malformed_json_returns_none_without_caching(http, cache):
    http.queue(FakeResponse(body=None, text="<html>not json</html>"))
    http.queue(FakeResponse(body=payload(intro=[{"start_ms": 1, "end_ms": 2}])))

    assert introdb.get_segments({"tmdb_id": 1}, 1, 1) is None
    assert cache.sets == []

    assert introdb.get_segments({"tmdb_id": 1}, 1, 1) is not None
    assert len(http.calls) == 2


def test_unexpected_json_payload_returns_none(http, cache):
    http.queue(FakeResponse(body=["unexpected"]))

    assert introdb.get_segments({"tmdb_id": 1}, 1, 1) is None
    assert cache.sets == []
