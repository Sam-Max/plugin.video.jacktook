"""Player-side AniSkip merge tests.

``fetch_introdb_segments`` is driven on a player built with ``object.__new__``
(its ``__init__`` needs a running Kodi), mirroring the defensive pattern the
player itself documents: state is provided, every external seam is stubbed, and
the merge only reacts to the anime marker carried in the playback data.
"""

import sys
from types import SimpleNamespace

import pytest

INTRODB_SEGMENTS = {"intro": {"start_ms": 1000, "end_ms": 90000}}
ANISKIP_SEGMENTS = {
    "intro": {"start_ms": 310571, "end_ms": 400571},
    "recap": {"start_ms": 132773, "end_ms": 201296},
}


@pytest.fixture
def fresh_player_module(monkeypatch):
    import xbmc

    import lib

    class FakeKodiPlayer:
        def __init__(self, *args, **kwargs):
            pass

    original_player_module = sys.modules.get("lib.player")

    monkeypatch.setattr(xbmc, "Player", FakeKodiPlayer)
    sys.modules.pop("lib.player", None)
    if hasattr(lib, "player"):
        delattr(lib, "player")

    try:
        from lib.player import JacktookPLayer

        yield JacktookPLayer
    finally:
        sys.modules.pop("lib.player", None)
        if hasattr(lib, "player"):
            delattr(lib, "player")

        if original_player_module is not None:
            sys.modules["lib.player"] = original_player_module
            lib.player = original_player_module


def _player(player_class, anime=False, total_time=145.0):
    player = object.__new__(player_class)
    player.data = {
        "ids": {"tmdb_id": 178319, "imdb_id": "tt2560140"},
        "tv_data": {"season": 3, "episode": 9},
    }
    if anime:
        player.data["anime"] = True
    player.skip_intro_segments = None
    player.skip_intro_handled = {}
    player.total_time = total_time
    return player


def _wire(monkeypatch, route=True, aniskip=ANISKIP_SEGMENTS):
    seen = {"route": 0, "skip_times": []}
    monkeypatch.setattr("lib.player.time.sleep", lambda seconds: None)
    monkeypatch.setattr(
        "lib.clients.introdb.get_segments", lambda ids, season, episode: INTRODB_SEGMENTS
    )
    if route:

        def fake_route(ids, season, episode, air_date=None):
            seen["route"] += 1
            return SimpleNamespace(mal_id=59193, absolute=58, kitsu_id=49002)

        monkeypatch.setattr("lib.anime.stream_target.resolve_anime_route", fake_route)
    monkeypatch.setattr(
        "lib.anime.providers.aniskip.get_skip_times",
        lambda mal_id, episode, length: (
            seen["skip_times"].append((mal_id, episode, length)) or aniskip
        ),
    )
    return seen


def test_anime_playback_merges_aniskip_over_introdb(fresh_player_module, monkeypatch):
    seen = _wire(monkeypatch)
    player = _player(fresh_player_module, anime=True)

    player.fetch_introdb_segments()

    assert seen["route"] == 1
    assert seen["skip_times"] == [(59193, 58, 145)]
    # AniSkip wins per type; IntroDB keeps types AniSkip does not carry.
    assert player.skip_intro_segments == {
        "intro": ANISKIP_SEGMENTS["intro"],
        "recap": ANISKIP_SEGMENTS["recap"],
    }


def test_non_anime_playback_never_resolves_the_route(fresh_player_module, monkeypatch):
    seen = _wire(monkeypatch)
    player = _player(fresh_player_module, anime=False)

    player.fetch_introdb_segments()

    assert seen["route"] == 0
    assert seen["skip_times"] == []
    assert player.skip_intro_segments == INTRODB_SEGMENTS


def test_unusable_route_keeps_introdb_segments(fresh_player_module, monkeypatch):
    _wire(monkeypatch)
    monkeypatch.setattr(
        "lib.anime.stream_target.resolve_anime_route",
        lambda ids, season, episode, air_date=None: SimpleNamespace(mal_id=59193, absolute=None),
    )
    player = _player(fresh_player_module, anime=True)

    player.fetch_introdb_segments()

    assert player.skip_intro_segments == INTRODB_SEGMENTS


def test_unknown_duration_keeps_introdb_segments(fresh_player_module, monkeypatch):
    seen = _wire(monkeypatch)
    player = _player(fresh_player_module, anime=True, total_time=0.0)

    player.fetch_introdb_segments()

    assert seen["skip_times"] == []
    assert player.skip_intro_segments == INTRODB_SEGMENTS


def test_empty_aniskip_keeps_introdb_segments(fresh_player_module, monkeypatch):
    seen = _wire(monkeypatch, aniskip=None)
    player = _player(fresh_player_module, anime=True)

    player.fetch_introdb_segments()

    assert seen["skip_times"] == [(59193, 58, 145)]
    assert player.skip_intro_segments == INTRODB_SEGMENTS
