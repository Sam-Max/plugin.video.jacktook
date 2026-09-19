"""Offline tests for the AniSkip v2 client.

Every HTTP call is stubbed through a fake ``requests.get`` and the module cache
is replaced with an in-memory double, so nothing here touches the network or
the Kodi property store.
"""

import pytest
import requests

from lib.anime.providers import aniskip

SKIP_TIMES_URL = "https://api.aniskip.com/v2/skip-times/21/1"

# Real AniSkip payload (shaped after One Piece MAL 21 episode 1, probed live).
ONE_PIECE_BODY = {
    "found": True,
    "results": [
        {
            "interval": {"startTime": 310.571, "endTime": 400.571},
            "skipType": "op",
            "episodeLength": 1443.984,
        },
        {
            "interval": {"startTime": 1396.006, "endTime": 1434.0},
            "skipType": "ed",
            "episodeLength": 1434.985,
        },
        {
            "interval": {"startTime": 132.773, "endTime": 201.296},
            "skipType": "recap",
            "episodeLength": 1444.0,
        },
    ],
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
        monkeypatch.setattr(aniskip.requests, "get", self.get)

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


@pytest.fixture
def cache(monkeypatch):
    fake = FakeCache()
    monkeypatch.setattr(aniskip, "_cache", fake)
    return fake


@pytest.fixture
def http(monkeypatch):
    return FakeHttp(monkeypatch)


# --- request shape ----------------------------------------------------------


def test_uses_the_v2_endpoint_with_types_and_length(http, cache):
    http.queue(FakeResponse(200, ONE_PIECE_BODY))

    aniskip.get_skip_times(21, 1, 1444.0)

    call = http.calls[0]
    assert call["url"] == SKIP_TIMES_URL
    assert call["params"]["types"] == ["op", "ed", "recap"]
    assert call["params"]["episodeLength"] == 1444.0


def test_invalid_arguments_never_perform_a_request(http):
    for mal_id, episode, length in ((0, 1, 1444), (21, 0, 1444), (21, 1, 0), (None, 1, 1444)):
        http.queue(FakeResponse(200, ONE_PIECE_BODY))
        assert aniskip.get_skip_times(mal_id, episode, length) is None
    assert http.calls == []


# --- response mapping ---------------------------------------------------------


def test_found_response_maps_op_ed_recap_to_addon_segments(http, cache):
    http.queue(FakeResponse(200, ONE_PIECE_BODY))

    segments = aniskip.get_skip_times(21, 1, 1444.0)

    assert sorted(segments) == ["intro", "outro", "recap"]
    assert segments["intro"] == {
        "start_ms": 310571,
        "end_ms": 400571,
        "start_sec": 310.571,
        "end_sec": 400.571,
    }
    assert segments["outro"]["start_ms"] == 1396006
    assert segments["recap"]["end_ms"] == 201296


def test_unknown_skip_types_are_ignored(http, cache):
    http.queue(
        FakeResponse(
            200,
            {
                "found": True,
                "results": [
                    {"interval": {"startTime": 1, "endTime": 2}, "skipType": "mixed-op"},
                    {"interval": {"startTime": 3, "endTime": 4}, "skipType": "whisper"},
                ],
            },
        )
    )

    assert aniskip.get_skip_times(21, 1, 1444.0) is None


def test_unusable_intervals_are_dropped(http, cache):
    http.queue(
        FakeResponse(
            200,
            {
                "found": True,
                "results": [
                    {"interval": {"startTime": 5, "endTime": 2}, "skipType": "op"},
                    {"interval": {"startTime": "x", "endTime": 9}, "skipType": "ed"},
                    {"interval": "nope", "skipType": "recap"},
                    {"interval": {"startTime": 7, "endTime": 9}, "skipType": "ed"},
                ],
            },
        )
    )

    segments = aniskip.get_skip_times(21, 1, 1444.0)

    assert sorted(segments) == ["outro"]
    assert segments["outro"]["start_sec"] == 7.0


def test_second_boundaries_are_derived_from_float_seconds(http, cache):
    http.queue(
        FakeResponse(
            200,
            {
                "found": True,
                "results": [{"interval": {"startTime": 0.5, "endTime": 90.25}, "skipType": "op"}],
            },
        )
    )

    segments = aniskip.get_skip_times(21, 1, 1440)

    assert segments["intro"]["start_ms"] == 500
    assert segments["intro"]["end_ms"] == 90250


# --- negative caching and failures -------------------------------------------


def test_404_is_negatively_cached(http, cache):
    http.queue(FakeResponse(404, {"found": False, "results": [], "statusCode": 404}))

    assert aniskip.get_skip_times(21, 1, 1444.0) is None
    assert aniskip.get_skip_times(21, 1, 1444.0) is None
    assert len(http.calls) == 1
    assert cache.sets[0][1] == aniskip._SENTINEL


def test_400_is_negatively_cached(http, cache):
    http.queue(FakeResponse(400, {"statusCode": 400, "message": "Bad Request"}))

    assert aniskip.get_skip_times(21, 1, 1444.0) is None
    assert len(http.calls) == 1
    assert cache.sets[0][1] == aniskip._SENTINEL


def test_found_false_is_negatively_cached(http, cache):
    http.queue(FakeResponse(200, {"found": False, "results": []}))

    assert aniskip.get_skip_times(21, 1, 1444.0) is None
    assert cache.sets[0][1] == aniskip._SENTINEL


def test_unexpected_status_is_not_negatively_cached(http):
    http.queue(FakeResponse(503, None, text="unavailable"))

    assert aniskip.get_skip_times(21, 1, 1444.0) is None
    assert len(http.calls) == 1


def test_network_error_returns_none(http):
    http.queue(requests.exceptions.Timeout("boom"))

    assert aniskip.get_skip_times(21, 1, 1444.0) is None
    assert http.calls


# --- merge policy -------------------------------------------------------------


def test_merge_prefers_aniskip_and_fills_from_introdb():
    base = {"intro": {"start_ms": 1}, "outro": {"start_ms": 2}}
    override = {"intro": {"start_ms": 100}, "recap": {"start_ms": 300}}

    merged = aniskip.merge_skip_segments(base, override)

    assert merged == {
        "intro": {"start_ms": 100},
        "outro": {"start_ms": 2},
        "recap": {"start_ms": 300},
    }


def test_merge_handles_missing_sources():
    assert aniskip.merge_skip_segments(None, {"intro": {"start_ms": 1}}) == {
        "intro": {"start_ms": 1}
    }
    assert aniskip.merge_skip_segments({"intro": {"start_ms": 1}}, None) == {
        "intro": {"start_ms": 1}
    }
    assert aniskip.merge_skip_segments(None, None) is None
    assert aniskip.merge_skip_segments({}, {}) is None
