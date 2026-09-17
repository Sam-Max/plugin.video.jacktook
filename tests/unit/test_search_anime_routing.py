"""Anime wiring through the search pipeline.

The anime marker on ``run_search_entry`` is the only gate for Kitsu routing: when
it is absent, or the route fails, every search must behave exactly as before, down
to the video id the Stremio addon client receives. These tests drive the real
``search_client`` pipeline (executor included) and watch the addon-client seam, so
a future call-site change fails loudly here instead of dying inside a swallowed
worker-thread exception.
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from lib.anime.stream_target import AnimeRoute
from lib.search import run_search_entry

IMDB_ID = "tt2560140"
KITSU_ID = 7442
ABSOLUTE_EPISODE = 5
SCOPED_ADDON_URL = "https://anime.example/manifest.json"
SEASON = 2
EPISODE = 3


class _AddonStub:
    """A stremio addon double that only declares the given stream id prefixes."""

    def __init__(self, prefixes):
        self._prefixes = set(prefixes)
        self.manifest = type("Manifest", (), {"name": "Anime Addon"})()

    def isSupported(self, resource, media_kind, prefix):
        return prefix in self._prefixes

    def key(self):
        return "anime.example"

    def url(self):
        return SCOPED_ADDON_URL


def _anime_route():
    return AnimeRoute(
        kitsu_id=KITSU_ID,
        absolute=ABSOLUTE_EPISODE,
        matched_by="season_episode",
        anilist_id=None,
        mal_id=None,
    )


def _run_anime_search(monkeypatch, addon, route, anime_marker="1"):
    """Run one scoped tv search through the real pipeline with a single addon.

    ``anime_marker`` mirrors the plugin-url values: ``"1"``, ``"0"``, or ``None``
    for a search without the key at all. ``route`` is what the anime gate resolves
    (or ``None``). Returns ``(route_calls, addon_client)`` for seam assertions.
    """
    params = {
        "query": "Attack on Titan",
        "mode": "tv",
        "media_type": "tv",
        "ids": json.dumps({"original_id": IMDB_ID, "imdb_id": IMDB_ID}),
        "tv_data": json.dumps({"season": SEASON, "episode": EPISODE}),
        "scoped_addon_url": SCOPED_ADDON_URL,
        "skip_cancel_on_back": True,
    }
    if anime_marker is not None:
        params["anime"] = anime_marker

    route_calls = []

    def resolve_route_spy(ids, season, episode, air_date=None):
        route_calls.append((ids, season, episode))
        return route

    addon_client = MagicMock()
    addon_client.return_value.search.return_value = []

    monkeypatch.setattr("lib.search._handle_super_quick_play", lambda params: False)
    monkeypatch.setattr("lib.search.resolve_anime_route", resolve_route_spy)
    monkeypatch.setattr("lib.search.set_content_type", lambda mode: None)
    monkeypatch.setattr("lib.search.set_watched_title", lambda *args, **kwargs: None)
    monkeypatch.setattr("lib.search.close_busy_dialog", lambda: None)
    monkeypatch.setattr("lib.search.reconcile_source_selection", lambda **kwargs: None)
    monkeypatch.setattr("lib.search.get_setting", lambda key, default=None: default)
    monkeypatch.setattr("lib.search.cache", SimpleNamespace(get=lambda key: None))
    monkeypatch.setattr("lib.search._infer_tmdb_year", lambda ids, mode: 2013)
    monkeypatch.setattr(
        "lib.search._build_title_fallback_queries", lambda *args, **kwargs: ["Attack on Titan"]
    )
    monkeypatch.setattr("lib.search._check_search_caches", lambda *args, **kwargs: None)
    monkeypatch.setattr("lib.search.get_addon_by_base_url", lambda url: addon)
    monkeypatch.setattr("lib.search.update_dialog", lambda *args, **kwargs: None)
    monkeypatch.setattr("lib.search.StremioAddonClient", addon_client)
    monkeypatch.setattr("lib.search.cache_results", lambda *args, **kwargs: None)
    monkeypatch.setattr("lib.search.notification", lambda *args, **kwargs: None)

    run_search_entry(params)
    return route_calls, addon_client


def test_marker_absent_skips_the_anime_gate_and_keeps_the_imdb_search(monkeypatch):
    addon = _AddonStub({"tt", "kitsu"})

    for anime_marker in (None, "0"):
        route_calls, addon_client = _run_anime_search(
            monkeypatch, addon, route=_anime_route(), anime_marker=anime_marker
        )

        assert route_calls == []
        search = addon_client.return_value.search
        search.assert_called_once_with(IMDB_ID, "tv", "tv", SEASON, EPISODE)
        assert "absolute_episode" not in search.call_args.kwargs


def test_kitsu_addon_receives_the_kitsu_video_id_and_absolute_episode(monkeypatch):
    addon = _AddonStub({"tt", "kitsu"})

    route_calls, addon_client = _run_anime_search(monkeypatch, addon, route=_anime_route())

    assert route_calls == [({"original_id": IMDB_ID, "imdb_id": IMDB_ID}, SEASON, EPISODE)]
    addon_client.assert_called_once_with(addon)
    # Pin the 4-tuple rebuild: the season is kept and the episode slot carries the
    # absolute number, so a call-site regression fails here instead of silently
    # searching with the wrong episode inside a worker thread.
    addon_client.return_value.search.assert_called_once_with(
        f"kitsu:{KITSU_ID}", "tv", "tv", SEASON, ABSOLUTE_EPISODE
    )


def test_addon_without_kitsu_keeps_the_original_imdb_id(monkeypatch):
    addon = _AddonStub({"tt"})

    _, addon_client = _run_anime_search(monkeypatch, addon, route=_anime_route())

    search = addon_client.return_value.search
    search.assert_called_once_with(IMDB_ID, "tv", "tv", SEASON, EPISODE)
    assert "absolute_episode" not in search.call_args.kwargs


def test_unresolved_route_keeps_the_original_imdb_id(monkeypatch):
    addon = _AddonStub({"tt", "kitsu"})

    route_calls, addon_client = _run_anime_search(monkeypatch, addon, route=None)

    assert route_calls == [({"original_id": IMDB_ID, "imdb_id": IMDB_ID}, SEASON, EPISODE)]
    search = addon_client.return_value.search
    search.assert_called_once_with(IMDB_ID, "tv", "tv", SEASON, EPISODE)
    assert "absolute_episode" not in search.call_args.kwargs
