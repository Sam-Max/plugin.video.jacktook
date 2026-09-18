import json
from unittest.mock import MagicMock

from lib.anime import stream_target
from lib.anime.episode_map import EpisodeCoordinates
from lib.anime.normalize import AnimeRecord

# Realistic id shapes: AniList/MAL 16498, TMDB 85937 and Kitsu 7442, with absolute
# episode 5. The values are obviously synthetic while staying plausible.
KITSU_ID = 7442
ANILIST_ID = 16498
MAL_ID = 16498


def _fail(*args, **kwargs):
    raise AssertionError("unexpected provider call")


class _IdentitySpy:
    """Records every ``resolve_identity`` call and returns a fixed record."""

    def __init__(self, record):
        self.record = record
        self.seeds = []

    def __call__(self, ids):
        self.seeds.append(ids)
        return self.record


class _EpisodeSpy:
    """Records every ``resolve_episode`` call and returns fixed coordinates."""

    def __init__(self, coordinates):
        self.coordinates = coordinates
        self.calls = []

    def __call__(self, ids, season, episode, air_date=None):
        self.calls.append((ids, season, episode, air_date))
        return self.coordinates


def _install_providers(monkeypatch, record, coordinates):
    identity_spy = _IdentitySpy(record)
    episode_spy = _EpisodeSpy(coordinates)
    monkeypatch.setattr(stream_target, "resolve_identity", identity_spy)
    monkeypatch.setattr(stream_target, "resolve_episode", episode_spy)
    return identity_spy, episode_spy


# ── resolve_anime_route: cheap rejects ───────────────────────


def test_resolve_anime_route_returns_none_without_ids(monkeypatch):
    monkeypatch.setattr(stream_target, "resolve_identity", _fail)
    monkeypatch.setattr(stream_target, "resolve_episode", _fail)

    assert stream_target.resolve_anime_route(None, 1, 1) is None
    assert stream_target.resolve_anime_route({}, 1, 1) is None
    assert stream_target.resolve_anime_route("garbage", 1, 1) is None
    assert stream_target.resolve_anime_route(42, 1, 1) is None
    assert stream_target.resolve_anime_route([("tmdb_id", 1)], 1, 1) is None


def test_resolve_anime_route_returns_none_without_a_usable_id(monkeypatch):
    monkeypatch.setattr(stream_target, "resolve_identity", _fail)
    monkeypatch.setattr(stream_target, "resolve_episode", _fail)

    assert stream_target.resolve_anime_route({"media_type": "tv"}, 1, 1) is None
    assert stream_target.resolve_anime_route({"simkl_id": 100}, 1, 1) is None
    assert stream_target.resolve_anime_route({"kitsu_id": KITSU_ID}, 1, 1) is None
    assert (
        stream_target.resolve_anime_route({"tmdb_id": None, "tvdb_id": "", "imdb_id": ""}, 1, 1)
        is None
    )


def test_resolve_anime_route_returns_none_for_uncoercible_coordinates(monkeypatch):
    monkeypatch.setattr(stream_target, "resolve_identity", _fail)
    monkeypatch.setattr(stream_target, "resolve_episode", _fail)

    assert stream_target.resolve_anime_route({"tmdb_id": 1}, None, 1) is None
    assert stream_target.resolve_anime_route({"tmdb_id": 1}, "x", 1) is None
    assert stream_target.resolve_anime_route({"tmdb_id": 1}, 1, None) is None
    assert stream_target.resolve_anime_route({"tmdb_id": 1}, 1, "x") is None
    assert stream_target.resolve_anime_route({"tmdb_id": 1}, 1, {}) is None


# ── resolve_anime_route: identity hand-off ───────────────────


def test_resolve_anime_route_returns_none_when_record_is_missing(monkeypatch):
    identity_spy, episode_spy = _install_providers(monkeypatch, None, None)

    assert stream_target.resolve_anime_route({"tmdb_id": 85937}, 1, 1) is None
    assert len(identity_spy.seeds) == 1
    assert episode_spy.calls == []


def test_resolve_anime_route_returns_none_without_kitsu_id(monkeypatch):
    record = AnimeRecord(anilist_id=ANILIST_ID, mal_id=MAL_ID)
    identity_spy, episode_spy = _install_providers(monkeypatch, record, None)

    assert stream_target.resolve_anime_route({"tmdb_id": 85937}, 1, 1) is None
    assert len(identity_spy.seeds) == 1
    assert episode_spy.calls == []


def test_resolve_anime_route_seeds_identity_with_exactly_four_keys(monkeypatch):
    identity_spy, _ = _install_providers(monkeypatch, None, None)

    stream_target.resolve_anime_route({"tmdb_id": 85937}, 1, 1)

    assert identity_spy.seeds == [
        {"tmdb_id": 85937, "tvdb_id": None, "imdb_id": None, "media_type": "tv"}
    ]


def test_resolve_anime_route_forwards_every_known_id_and_the_tv_hint(monkeypatch):
    identity_spy, _ = _install_providers(monkeypatch, None, None)

    stream_target.resolve_anime_route(
        {
            "tmdb_id": 85937,
            "tvdb_id": 41135,
            "imdb_id": "tt2560140",
            "anilist_id": ANILIST_ID,
            "mal_id": MAL_ID,
            "kitsu_id": KITSU_ID,
        },
        1,
        1,
    )

    assert identity_spy.seeds == [
        {
            "tmdb_id": 85937,
            "tvdb_id": 41135,
            "imdb_id": "tt2560140",
            "media_type": "tv",
        }
    ]


def test_resolve_anime_route_passes_record_ids_to_episode(monkeypatch):
    record = AnimeRecord(anilist_id=ANILIST_ID, mal_id=MAL_ID, kitsu_id=KITSU_ID)
    coordinates = EpisodeCoordinates(absolute=5, season=1, episode=5, matched_by="season_episode")
    _, episode_spy = _install_providers(monkeypatch, record, coordinates)

    stream_target.resolve_anime_route({"tmdb_id": 85937}, 1, 5)

    assert episode_spy.calls == [({"anilist_id": ANILIST_ID, "mal_id": MAL_ID}, 1, 5, None)]


def test_resolve_anime_route_forwards_air_date(monkeypatch):
    record = AnimeRecord(anilist_id=ANILIST_ID, mal_id=MAL_ID, kitsu_id=KITSU_ID)
    coordinates = EpisodeCoordinates(absolute=1, matched_by="air_date")
    _, episode_spy = _install_providers(monkeypatch, record, coordinates)

    stream_target.resolve_anime_route({"tmdb_id": 85937}, 1, 1, air_date="2013-04-07")

    assert episode_spy.calls == [({"anilist_id": ANILIST_ID, "mal_id": MAL_ID}, 1, 1, "2013-04-07")]


def test_resolve_anime_route_accepts_an_record_without_ids(monkeypatch):
    record = AnimeRecord(kitsu_id=KITSU_ID)
    coordinates = EpisodeCoordinates(absolute=5)
    _, episode_spy = _install_providers(monkeypatch, record, coordinates)

    route = stream_target.resolve_anime_route({"tmdb_id": 85937}, 1, 5)

    assert episode_spy.calls == [({"anilist_id": None, "mal_id": None}, 1, 5, None)]
    assert route is not None
    assert route.anilist_id is None
    assert route.mal_id is None


# ── resolve_anime_route: route assembly ──────────────────────


def test_resolve_anime_route_carries_coordinates(monkeypatch):
    record = AnimeRecord(anilist_id=ANILIST_ID, mal_id=MAL_ID, kitsu_id=KITSU_ID)
    coordinates = EpisodeCoordinates(absolute=5, season=1, episode=5, matched_by="season_episode")
    _install_providers(monkeypatch, record, coordinates)

    route = stream_target.resolve_anime_route({"tmdb_id": 85937}, 1, 5)

    assert route == stream_target.AnimeRoute(
        kitsu_id=KITSU_ID,
        absolute=5,
        matched_by="season_episode",
        anilist_id=ANILIST_ID,
        mal_id=MAL_ID,
    )


def test_resolve_anime_route_keeps_route_when_coordinates_are_missing(monkeypatch):
    record = AnimeRecord(anilist_id=ANILIST_ID, mal_id=MAL_ID, kitsu_id=KITSU_ID)
    _install_providers(monkeypatch, record, None)

    route = stream_target.resolve_anime_route({"tmdb_id": 85937}, 1, 5)

    assert route is not None
    assert route.kitsu_id == KITSU_ID
    assert route.absolute is None
    assert route.matched_by is None


def test_resolve_anime_route_keeps_route_when_absolute_is_missing(monkeypatch):
    record = AnimeRecord(anilist_id=ANILIST_ID, mal_id=MAL_ID, kitsu_id=KITSU_ID)
    coordinates = EpisodeCoordinates(season=1, episode=5, matched_by="season_episode")
    _install_providers(monkeypatch, record, coordinates)

    route = stream_target.resolve_anime_route({"tmdb_id": 85937}, 1, 5)

    assert route is not None
    assert route.absolute is None
    assert route.matched_by == "season_episode"


# ── resolve_anime_route: never raises ────────────────────────


def test_resolve_anime_route_swallows_identity_exceptions(monkeypatch):
    def boom(ids):
        raise RuntimeError("boom")

    monkeypatch.setattr(stream_target, "resolve_identity", boom)
    monkeypatch.setattr(stream_target, "resolve_episode", _fail)

    assert stream_target.resolve_anime_route({"tmdb_id": 85937}, 1, 1) is None


def test_resolve_anime_route_swallows_episode_exceptions(monkeypatch):
    record = AnimeRecord(anilist_id=ANILIST_ID, mal_id=MAL_ID, kitsu_id=KITSU_ID)
    monkeypatch.setattr(stream_target, "resolve_identity", lambda ids: record)

    def boom(ids, season, episode, air_date=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(stream_target, "resolve_episode", boom)

    assert stream_target.resolve_anime_route({"tmdb_id": 85937}, 1, 1) is None


def test_resolve_anime_route_swallows_garbage_coordinates(monkeypatch):
    record = AnimeRecord(anilist_id=ANILIST_ID, mal_id=MAL_ID, kitsu_id=KITSU_ID)
    _install_providers(monkeypatch, record, "garbage")

    route = stream_target.resolve_anime_route({"tmdb_id": 85937}, 1, 1)

    assert route is not None
    assert route.absolute is None
    assert route.matched_by is None


# ── pick_kitsu_target ────────────────────────────────────────


def test_pick_kitsu_target_returns_none_without_route():
    assert stream_target.pick_kitsu_target(None, 1, 5) is None


def test_pick_kitsu_target_requires_a_positive_absolute():
    for absolute in (None, 0, -3, "x", {}, 0.5):
        route = stream_target.AnimeRoute(
            kitsu_id=KITSU_ID, absolute=absolute, matched_by=None, anilist_id=None, mal_id=None
        )

        assert stream_target.pick_kitsu_target(route, 1, 5) is None


def test_pick_kitsu_target_requires_a_positive_kitsu_id():
    for kitsu_id in (None, 0, -1, "x", {}):
        route = stream_target.AnimeRoute(
            kitsu_id=kitsu_id, absolute=5, matched_by=None, anilist_id=None, mal_id=None
        )

        assert stream_target.pick_kitsu_target(route, 1, 5) is None


def test_pick_kitsu_target_builds_the_kitsu_video_id():
    route = stream_target.AnimeRoute(
        kitsu_id=KITSU_ID,
        absolute=5,
        matched_by="season_episode",
        anilist_id=ANILIST_ID,
        mal_id=MAL_ID,
    )

    target = stream_target.pick_kitsu_target(route, 1, 5)

    assert target == stream_target.StreamTarget(
        video_id="kitsu:7442", episode=5, kind="kitsu", absolute=5
    )
    assert target is not None
    assert target.episode == target.absolute


def test_pick_kitsu_target_coerces_string_values():
    route = stream_target.AnimeRoute(
        kitsu_id="7442", absolute="5", matched_by=None, anilist_id=None, mal_id=None
    )

    target = stream_target.pick_kitsu_target(route, 1, 5)

    assert target is not None
    assert target.video_id == "kitsu:7442"
    assert target.episode == 5


def test_pick_kitsu_target_ignores_season_and_episode():
    route = stream_target.AnimeRoute(
        kitsu_id=KITSU_ID, absolute=5, matched_by=None, anilist_id=None, mal_id=None
    )

    target = stream_target.pick_kitsu_target(route, 9, 99)

    assert target is not None
    assert target.episode == 5
    assert target == stream_target.pick_kitsu_target(route, 1, 5)


def test_pick_kitsu_target_is_pure(monkeypatch):
    monkeypatch.setattr(stream_target, "resolve_identity", _fail)
    monkeypatch.setattr(stream_target, "resolve_episode", _fail)
    route = stream_target.AnimeRoute(
        kitsu_id=KITSU_ID, absolute=5, matched_by=None, anilist_id=None, mal_id=None
    )

    assert stream_target.pick_kitsu_target(route, 1, 5) is not None


# ── supports_kitsu_target ────────────────────────────────────


def test_supports_kitsu_target_for_a_real_kitsu_target():
    route = stream_target.AnimeRoute(
        kitsu_id=KITSU_ID, absolute=5, matched_by=None, anilist_id=None, mal_id=None
    )

    assert stream_target.supports_kitsu_target(stream_target.pick_kitsu_target(route, 1, 5)) is True


def test_supports_kitsu_target_rejects_missing_or_foreign_targets():
    assert stream_target.supports_kitsu_target(None) is False
    assert (
        stream_target.supports_kitsu_target(
            stream_target.StreamTarget(video_id="tvdb:1", episode=1, kind="tvdb", absolute=1)
        )
        is False
    )
    assert (
        stream_target.supports_kitsu_target(
            stream_target.StreamTarget(video_id="kitsu:7442", episode=0, kind="kitsu", absolute=0)
        )
        is False
    )


# ── air-date wiring into the search request ──────────────────

# The air date is the only signal that resolves One Piece's TMDB (season 23, episode
# 1160) against AniZip's AniDB entries, so it has to travel from the episode list into
# the search request and on to the route resolver. These two tests cover the two hops
# the anime routing tests above cannot see: the episode view building ``tv_data`` and
# the search entry forwarding it.


class _EpisodeStub:
    """Minimal TMDB episode stand-in with the attributes the episode view reads."""

    def __init__(self, name, episode_number, air_date):
        self.name = name
        self.episode_number = episode_number
        self.air_date = air_date


def _run_process_episode(monkeypatch, air_date):
    from lib.utils.views import shows

    urls = []

    def fake_build_url(action, **params):
        urls.append((action, params))
        return f"plugin://plugin.video.jacktook/?action={action}"

    monkeypatch.setattr(shows, "build_url", fake_build_url)
    monkeypatch.setattr(shows, "make_list_item", lambda **kwargs: MagicMock())
    monkeypatch.setattr(shows, "set_media_infoTag", lambda *args, **kwargs: None)
    monkeypatch.setattr(shows, "add_tmdb_episode_context_menu", lambda *args, **kwargs: [])
    monkeypatch.setattr(shows, "is_trakt_auth", lambda: False)
    monkeypatch.setattr(shows, "add_simkl_history_context_menu", lambda *args, **kwargs: [])
    monkeypatch.setattr(shows, "add_nuvio_history_context_menu", lambda *args, **kwargs: [])

    shows._process_episode(
        _EpisodeStub("An Encounter on a Snowfield", 1160, air_date),
        "One Piece",
        23,
        {"tmdb_id": 37854},
        "tv",
        "tv",
        None,
        True,
    )

    assert len(urls) == 1
    action, params = urls[0]
    assert action == "search"
    return params


def test_process_episode_carries_the_air_date_into_tv_data(monkeypatch):
    params = _run_process_episode(monkeypatch, "2026-05-03")

    assert params["tv_data"]["air_date"] == "2026-05-03"
    assert params["tv_data"]["season"] == 23
    assert params["tv_data"]["episode"] == 1160


def test_process_episode_tolerates_a_missing_air_date(monkeypatch):
    params = _run_process_episode(monkeypatch, None)

    assert params["tv_data"]["air_date"] is None


def test_run_search_entry_forwards_the_tv_data_air_date_to_the_route(monkeypatch):
    from lib import search as search_module

    calls = []

    def spy_resolve_anime_route(ids, season, episode, air_date=None):
        calls.append((ids, season, episode, air_date))
        return None

    monkeypatch.setattr(search_module, "resolve_anime_route", spy_resolve_anime_route)
    monkeypatch.setattr(search_module, "get_setting", lambda key, default=None: default)
    monkeypatch.setattr(search_module, "set_content_type", lambda *args, **kwargs: None)
    monkeypatch.setattr(search_module, "set_watched_title", lambda *args, **kwargs: None)
    monkeypatch.setattr(search_module, "search_client", lambda *args, **kwargs: [])
    monkeypatch.setattr(search_module, "notification", lambda *args, **kwargs: None)
    monkeypatch.setattr(search_module, "cancel_playback", lambda *args, **kwargs: None)

    search_module.run_search_entry(
        {
            "query": "One Piece",
            "mode": "tv",
            "media_type": "tv",
            "ids": json.dumps({"tmdb_id": 37854, "tvdb_id": 81797, "imdb_id": "tt0388629"}),
            "tv_data": json.dumps(
                {
                    "name": "An Encounter on a Snowfield",
                    "season": 23,
                    "episode": 1160,
                    "air_date": "2026-05-03",
                }
            ),
            "anime": "1",
            "skip_cancel_on_back": True,
        }
    )

    assert calls == [
        (
            {"tmdb_id": 37854, "tvdb_id": 81797, "imdb_id": "tt0388629"},
            23,
            1160,
            "2026-05-03",
        )
    ]


# ── resolve_anime_route: per-season (multi-cour) fallback ────

# Live-verified Mushoku Tensei shapes: the identity record is the base cour
# entry (Simkl 1059371, which covers season 1 only) and season 3 lives in the
# sequel entry 2832226 with its own AniList/MAL/Kitsu ids.

BASE_SEASON_IDS = {
    "simkl_id": 1059371,
    "anilist_id": 108465,
    "mal_id": 39535,
    "kitsu_id": 42323,
}
SEASON_THREE_IDS = {
    "simkl_id": 2832226,
    "anilist_id": 178789,
    "mal_id": 59193,
    "kitsu_id": 49002,
}


def _multi_cour_record():
    return AnimeRecord(anilist_id=108465, mal_id=39535, kitsu_id=42323, simkl_id=1059371)


def test_resolve_anime_route_reroutes_through_the_season_entry(monkeypatch):
    record = _multi_cour_record()
    monkeypatch.setattr(stream_target, "resolve_identity", _IdentitySpy(record))

    def fake_resolve_episode(ids, season, episode, air_date=None):
        if ids.get("anilist_id") == 178789:
            return EpisodeCoordinates(absolute=25, season=3, episode=1, matched_by="season_episode")
        # The base entry's AniZip index only covers season 1.
        return None

    monkeypatch.setattr(stream_target, "resolve_episode", fake_resolve_episode)

    season_calls = []

    def fake_resolve_season_entry(base_simkl_id, season):
        season_calls.append((base_simkl_id, season))
        return dict(SEASON_THREE_IDS)

    monkeypatch.setattr(stream_target, "resolve_season_entry", fake_resolve_season_entry)

    route = stream_target.resolve_anime_route({"tmdb_id": 1059371}, 3, 1)

    assert season_calls == [(1059371, 3)]
    assert route == stream_target.AnimeRoute(
        kitsu_id=49002,
        absolute=25,
        matched_by="season_episode",
        anilist_id=178789,
        mal_id=59193,
    )
    assert stream_target.pick_kitsu_target(route, 3, 1) == stream_target.StreamTarget(
        video_id="kitsu:49002", episode=25, kind="kitsu", absolute=25
    )


def test_resolve_anime_route_keeps_the_base_route_when_the_season_entry_cannot_match(
    monkeypatch,
):
    # The sequel entry resolves but its index also lacks the episode: the
    # fallback degrades to None and the base route stays. With absolute None,
    # pick_kitsu_target yields None, so the caller keeps its existing id chain
    # (including the imdb seed) — the pre-existing fallback contract.
    record = _multi_cour_record()
    monkeypatch.setattr(stream_target, "resolve_identity", _IdentitySpy(record))
    monkeypatch.setattr(
        stream_target, "resolve_episode", lambda ids, season, episode, air_date=None: None
    )
    monkeypatch.setattr(
        stream_target,
        "resolve_season_entry",
        lambda base_simkl_id, season: dict(SEASON_THREE_IDS),
    )

    route = stream_target.resolve_anime_route({"tmdb_id": 1059371}, 3, 1)

    assert route == stream_target.AnimeRoute(
        kitsu_id=42323, absolute=None, matched_by=None, anilist_id=108465, mal_id=39535
    )
    assert stream_target.pick_kitsu_target(route, 3, 1) is None


def test_resolve_anime_route_does_not_rematch_the_base_entry(monkeypatch):
    # The season is covered by the base entry, so resolve_season_entry hands
    # back the base ids: re-running the episode map on them cannot produce
    # different coordinates and must not happen.
    record = _multi_cour_record()
    monkeypatch.setattr(stream_target, "resolve_identity", _IdentitySpy(record))
    episode_spy = _EpisodeSpy(None)
    monkeypatch.setattr(stream_target, "resolve_episode", episode_spy)
    monkeypatch.setattr(
        stream_target,
        "resolve_season_entry",
        lambda base_simkl_id, season: dict(BASE_SEASON_IDS),
    )

    route = stream_target.resolve_anime_route({"tmdb_id": 1059371}, 3, 1)

    assert len(episode_spy.calls) == 1
    assert route is not None
    assert route.kitsu_id == 42323
    assert route.absolute is None


def test_resolve_anime_route_keeps_the_base_route_without_an_entry_kitsu_id(monkeypatch):
    record = _multi_cour_record()
    monkeypatch.setattr(stream_target, "resolve_identity", _IdentitySpy(record))

    def fake_resolve_episode(ids, season, episode, air_date=None):
        if ids.get("anilist_id") == 178789:
            return EpisodeCoordinates(absolute=25, season=3, episode=1, matched_by="air_date")
        return None

    monkeypatch.setattr(stream_target, "resolve_episode", fake_resolve_episode)
    entry = dict(SEASON_THREE_IDS)
    entry["kitsu_id"] = None
    monkeypatch.setattr(stream_target, "resolve_season_entry", lambda base_simkl_id, season: entry)

    route = stream_target.resolve_anime_route({"tmdb_id": 1059371}, 3, 1)

    assert route is not None
    assert route.kitsu_id == 42323
    assert route.absolute is None


def test_resolve_anime_route_skips_the_season_fallback_without_simkl_id(monkeypatch):
    record = AnimeRecord(anilist_id=ANILIST_ID, mal_id=MAL_ID, kitsu_id=KITSU_ID)
    monkeypatch.setattr(stream_target, "resolve_identity", _IdentitySpy(record))
    monkeypatch.setattr(stream_target, "resolve_episode", lambda *args, **kwargs: None)
    monkeypatch.setattr(stream_target, "resolve_season_entry", _fail)

    route = stream_target.resolve_anime_route({"tmdb_id": 85937}, 1, 5)

    assert route is not None
    assert route.kitsu_id == KITSU_ID
    assert route.absolute is None


def test_resolve_anime_route_skips_the_season_fallback_for_a_non_positive_season(
    monkeypatch,
):
    record = _multi_cour_record()
    monkeypatch.setattr(stream_target, "resolve_identity", _IdentitySpy(record))
    monkeypatch.setattr(stream_target, "resolve_episode", lambda *args, **kwargs: None)
    monkeypatch.setattr(stream_target, "resolve_season_entry", _fail)

    # Season 0 passes the coarse coercibility gate but is not a usable season.
    route = stream_target.resolve_anime_route({"tmdb_id": 1059371}, 0, 1)

    assert route is not None
    assert route.kitsu_id == 42323
    assert route.absolute is None


def test_resolve_anime_route_keeps_the_base_route_when_the_fallback_raises(monkeypatch):
    record = _multi_cour_record()
    monkeypatch.setattr(stream_target, "resolve_identity", _IdentitySpy(record))
    monkeypatch.setattr(stream_target, "resolve_episode", lambda *args, **kwargs: None)

    def boom(base_simkl_id, season):
        raise RuntimeError("boom")

    monkeypatch.setattr(stream_target, "resolve_season_entry", boom)

    route = stream_target.resolve_anime_route({"tmdb_id": 1059371}, 3, 1)

    # A fallback failure must degrade to the base route, never to None: the
    # base route was exactly what the pre-fallback behavior returned.
    assert route is not None
    assert route.kitsu_id == 42323
    assert route.absolute is None
