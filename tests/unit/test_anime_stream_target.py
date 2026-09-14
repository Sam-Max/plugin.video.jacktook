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
