"""Season-name anchoring for multi-cour anime.

TMDB names a season after the arc it adapts and can cover several AniList cours at
once, while each cour keeps its own entry and its own episode numbering. These tests
pin the mapping from (TMDB season name, episode) to the cour that holds the episode,
using the real Bleach: Thousand-Year Blood War shape: 13 + 13 + 14 + 10 episodes for
the four cours TMDB flattens into season 2.
"""

import json

from lib.anime import stream_target
from lib.anime.normalize import AnimeRecord

BASE_KITSU_ID = 244
COUR_KITSU_ID = 49444
COUR_ANILIST_ID = 185874
COUR_MAL_ID = 60636

TYBW_COURS = [
    {
        "id": 116674,
        "idMal": 41467,
        "episodes": 13,
        "startDate": {"year": 2022},
        "title": {
            "romaji": "BLEACH: Sennen Kessen-hen",
            "english": "BLEACH: Thousand-Year Blood War",
        },
    },
    {
        "id": 159322,
        "idMal": 53998,
        "episodes": 13,
        "startDate": {"year": 2023},
        "title": {"english": "BLEACH: Thousand-Year Blood War - The Separation"},
    },
    {
        "id": 169755,
        "idMal": 56784,
        "episodes": 14,
        "startDate": {"year": 2024},
        "title": {"english": "BLEACH: Thousand-Year Blood War - The Conflict"},
    },
    {
        "id": COUR_ANILIST_ID,
        "idMal": COUR_MAL_ID,
        "episodes": 10,
        "startDate": {"year": 2026},
        "title": {"english": "BLEACH: Thousand-Year Blood War - The Calamity"},
    },
]

BASE_RECORD = AnimeRecord(
    anilist_id=269,
    mal_id=269,
    kitsu_id=BASE_KITSU_ID,
    title_en="Bleach",
)
COUR_RECORD = AnimeRecord(
    anilist_id=COUR_ANILIST_ID,
    mal_id=COUR_MAL_ID,
    kitsu_id=COUR_KITSU_ID,
    title_en="Bleach: Thousand-Year Blood War - The Calamity",
)


class _SearchSpy:
    """Records every AniList search and returns a fixed media list."""

    def __init__(self, results):
        self.results = results
        self.queries = []

    def __call__(self, query, page=1, per_page=15):
        self.queries.append(query)
        return self.results


class _IdentityMap:
    """Returns a per-anilist-id record, falling back to the base record."""

    def __init__(self, base, by_anilist_id):
        self.base = base
        self.by_anilist_id = by_anilist_id
        self.seeds = []

    def __call__(self, ids):
        self.seeds.append(ids)
        anilist_id = ids.get("anilist_id") if isinstance(ids, dict) else None
        if anilist_id is not None:
            return self.by_anilist_id.get(anilist_id)
        return self.base


def _patch_search(monkeypatch, results):
    from lib.anime.providers import anilist

    spy = _SearchSpy(results)
    monkeypatch.setattr(anilist, "search_anime", spy)
    return spy


# ── resolve_season_anchor: cheap rejects ─────────────────────


def test_generic_season_names_never_search(monkeypatch):
    spy = _patch_search(monkeypatch, TYBW_COURS)

    for name in ("", None, "Season 2", "season 12", "Specials", "Extras"):
        assert stream_target.resolve_season_anchor(BASE_RECORD, name, 49) is None

    assert spy.queries == []


def test_anchor_requires_an_episode_number_and_a_title(monkeypatch):
    spy = _patch_search(monkeypatch, TYBW_COURS)

    assert stream_target.resolve_season_anchor(BASE_RECORD, "Thousand-Year Blood War", None) is None
    assert stream_target.resolve_season_anchor(BASE_RECORD, "Thousand-Year Blood War", 0) is None
    assert stream_target.resolve_season_anchor(AnimeRecord(), "Thousand-Year Blood War", 49) is None

    assert spy.queries == []


def test_anchor_returns_none_without_candidates(monkeypatch):
    _patch_search(monkeypatch, [])

    assert stream_target.resolve_season_anchor(BASE_RECORD, "Thousand-Year Blood War", 49) is None


def test_anchor_ignores_candidates_without_the_season_tokens(monkeypatch):
    _patch_search(
        monkeypatch,
        [
            {"id": 1, "idMal": 1, "episodes": 50, "title": {"english": "Some Other Show"}},
            {"id": 2, "idMal": 2, "episodes": 12, "title": {"english": "Thousand-Year Blood War"}},
        ],
    )

    anchor = stream_target.resolve_season_anchor(BASE_RECORD, "Thousand-Year Blood War", 49)

    # Only the candidate carrying every distinctive token survives the filter, and
    # it holds 12 episodes, so episode 49 is past its end.
    assert anchor is None


# ── resolve_season_anchor: cour selection ────────────────────


def test_anchor_walks_the_cours_in_airing_order(monkeypatch):
    _patch_search(monkeypatch, TYBW_COURS)

    anchor = stream_target.resolve_season_anchor(BASE_RECORD, "Thousand-Year Blood War", 49)

    # 13 + 13 + 14 = 40 episodes before The Calamity, so episode 49 is its 9th.
    assert anchor is not None
    assert anchor.anilist_id == COUR_ANILIST_ID
    assert anchor.mal_id == COUR_MAL_ID
    assert anchor.local_episode == 9
    assert anchor.matched_by == "season_name"


def test_anchor_selects_the_first_cour_for_an_early_episode(monkeypatch):
    _patch_search(monkeypatch, TYBW_COURS)

    anchor = stream_target.resolve_season_anchor(BASE_RECORD, "Thousand-Year Blood War", 5)

    assert anchor is not None
    assert anchor.anilist_id == 116674
    assert anchor.local_episode == 5


def test_anchor_selects_the_boundary_cour_episode(monkeypatch):
    _patch_search(monkeypatch, TYBW_COURS)

    # Episode 41 is the first of the fourth cour, and 40 the last of the third.
    assert (
        stream_target.resolve_season_anchor(
            BASE_RECORD, "Thousand-Year Blood War", 41
        ).local_episode
        == 1
    )
    assert (
        stream_target.resolve_season_anchor(BASE_RECORD, "Thousand-Year Blood War", 40).anilist_id
        == 169755
    )


def test_anchor_returns_none_past_the_last_cour(monkeypatch):
    _patch_search(monkeypatch, TYBW_COURS)

    assert stream_target.resolve_season_anchor(BASE_RECORD, "Thousand-Year Blood War", 51) is None


def test_anchor_orders_cours_by_start_year_not_by_search_order(monkeypatch):
    _patch_search(monkeypatch, list(reversed(TYBW_COURS)))

    anchor = stream_target.resolve_season_anchor(BASE_RECORD, "Thousand-Year Blood War", 49)

    assert anchor is not None
    assert anchor.anilist_id == COUR_ANILIST_ID
    assert anchor.local_episode == 9


def test_anchor_never_raises_when_the_provider_raises(monkeypatch):
    from lib.anime.providers import anilist

    def boom(*args, **kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setattr(anilist, "search_anime", boom)

    assert stream_target.resolve_season_anchor(BASE_RECORD, "Thousand-Year Blood War", 49) is None


# ── resolve_anime_route: anchoring in the route ──────────────


def _patch_identity(monkeypatch, base=BASE_RECORD, cour=COUR_RECORD):
    identity = _IdentityMap(base, {COUR_ANILIST_ID: cour})
    monkeypatch.setattr(stream_target, "resolve_identity", identity)
    return identity


def test_route_uses_the_anchored_cour_and_its_local_episode(monkeypatch):
    _patch_search(monkeypatch, TYBW_COURS)
    identity = _patch_identity(monkeypatch)
    monkeypatch.setattr(
        stream_target, "resolve_episode", lambda *args, **kwargs: _fail("episode map unused")
    )

    route = stream_target.resolve_anime_route(
        {"tmdb_id": 30984},
        2,
        49,
        "2026-10-20",
        "Thousand-Year Blood War",
    )

    assert route is not None
    assert route.kitsu_id == COUR_KITSU_ID
    assert route.absolute == 9
    assert route.matched_by == "season_name"
    assert route.anilist_id == COUR_ANILIST_ID
    assert route.mal_id == COUR_MAL_ID
    # The base record is resolved first through the fixed identity seed, then the
    # anchored cour by its own ids.
    assert identity.seeds == [
        {"tmdb_id": 30984, "tvdb_id": None, "imdb_id": None, "media_type": "tv"},
        {"anilist_id": COUR_ANILIST_ID, "mal_id": COUR_MAL_ID},
    ]


def test_route_falls_back_when_the_cour_has_no_kitsu_id(monkeypatch):
    _patch_search(monkeypatch, TYBW_COURS)
    _patch_identity(monkeypatch, cour=AnimeRecord(anilist_id=COUR_ANILIST_ID, mal_id=COUR_MAL_ID))
    monkeypatch.setattr(
        stream_target,
        "resolve_episode",
        lambda *args, **kwargs: _coordinates(absolute=268),
    )

    route = stream_target.resolve_anime_route(
        {"tmdb_id": 30984}, 2, 49, "2026-10-20", "Thousand-Year Blood War"
    )

    assert route is not None
    assert route.kitsu_id == BASE_KITSU_ID
    assert route.absolute == 268


def test_route_without_a_season_name_keeps_the_existing_path(monkeypatch):
    spy = _patch_search(monkeypatch, TYBW_COURS)
    _patch_identity(monkeypatch)
    monkeypatch.setattr(
        stream_target,
        "resolve_episode",
        lambda *args, **kwargs: _coordinates(absolute=49),
    )

    route = stream_target.resolve_anime_route({"tmdb_id": 30984}, 2, 49, "2026-10-20")

    assert route is not None
    assert route.kitsu_id == BASE_KITSU_ID
    assert route.absolute == 49
    assert spy.queries == []


def test_generic_season_name_keeps_the_existing_path(monkeypatch):
    spy = _patch_search(monkeypatch, TYBW_COURS)
    _patch_identity(monkeypatch)
    monkeypatch.setattr(
        stream_target,
        "resolve_episode",
        lambda *args, **kwargs: _coordinates(absolute=12),
    )

    route = stream_target.resolve_anime_route({"tmdb_id": 30984}, 1, 12, "2026-10-20", "Season 1")

    assert route is not None
    assert route.absolute == 12
    assert spy.queries == []


def test_search_forwards_the_season_name_to_the_route(monkeypatch):
    from lib import search as search_module

    calls = []

    def spy_resolve_anime_route(ids, season, episode, air_date=None, season_name=None):
        calls.append(season_name)
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
            "query": "Bleach",
            "mode": "tv",
            "media_type": "tv",
            "ids": json.dumps({"tmdb_id": 30984}),
            "tv_data": json.dumps(
                {
                    "name": "THE BLADE",
                    "season": 2,
                    "episode": 49,
                    "air_date": "2026-10-20",
                    "season_name": "Thousand-Year Blood War",
                }
            ),
            "anime": "1",
            "skip_cancel_on_back": True,
        }
    )

    assert calls == ["Thousand-Year Blood War"]


def _fail(message):
    raise AssertionError(message)


def _coordinates(absolute):
    from lib.anime.episode_map import EpisodeCoordinates

    return EpisodeCoordinates(absolute=absolute, season=1, episode=absolute)


# ── search wiring: the cour-local number travels to the debrid resolver ──────


def _run_search_with_route(monkeypatch, route, tv_data_extra=None):
    from lib import search as search_module
    from lib.anime.stream_target import AnimeRoute

    captured = {}

    def spy_show_source_select(results, mode, ids, tv_data, *args, **kwargs):
        captured["tv_data"] = dict(tv_data)
        return True

    monkeypatch.setattr(search_module, "resolve_anime_route", lambda *a, **k: route)
    monkeypatch.setattr(search_module, "auto_play_enabled", lambda: False)
    monkeypatch.setattr(search_module, "show_source_select", spy_show_source_select)
    monkeypatch.setattr(search_module, "search_client", lambda *a, **k: [object()])
    monkeypatch.setattr(search_module, "_process_search_results", lambda *a, **k: [object()])
    monkeypatch.setattr(search_module, "get_setting", lambda key, default=None: default)
    monkeypatch.setattr(search_module, "set_content_type", lambda *a, **k: None)
    monkeypatch.setattr(search_module, "set_watched_title", lambda *a, **k: None)
    monkeypatch.setattr(search_module, "notification", lambda *a, **k: None)
    monkeypatch.setattr(search_module, "cancel_playback", lambda *a, **k: None)
    monkeypatch.setattr(search_module, "_check_search_caches", lambda *a, **k: None)

    tv_data = {
        "name": "THE BLADE",
        "season": 2,
        "episode": 49,
        "air_date": "2026-10-20",
        "season_name": "Thousand-Year Blood War",
    }
    tv_data.update(tv_data_extra or {})

    search_module.run_search_entry(
        {
            "query": "Bleach",
            "mode": "tv",
            "media_type": "tv",
            "ids": json.dumps({"tmdb_id": 30984}),
            "tv_data": json.dumps(tv_data),
            "anime": "1",
            "skip_cancel_on_back": True,
        }
    )
    return captured


def test_search_carries_the_cour_local_episode_into_tv_data(monkeypatch):
    from lib.anime.stream_target import AnimeRoute

    captured = _run_search_with_route(
        monkeypatch,
        AnimeRoute(
            kitsu_id=COUR_KITSU_ID,
            absolute=9,
            matched_by="season_name",
            anilist_id=COUR_ANILIST_ID,
            mal_id=COUR_MAL_ID,
        ),
    )

    assert captured["tv_data"]["anime_episode"] == 9
    # The TMDB coordinates stay untouched for everything that reads them.
    assert captured["tv_data"]["episode"] == 49
    assert captured["tv_data"]["season"] == 2


def test_search_does_not_carry_a_franchise_absolute_as_the_cour_episode(monkeypatch):
    from lib.anime.stream_target import AnimeRoute

    captured = _run_search_with_route(
        monkeypatch,
        AnimeRoute(
            kitsu_id=244,
            absolute=268,
            matched_by="air_date",
            anilist_id=269,
            mal_id=269,
        ),
    )

    assert "anime_episode" not in captured["tv_data"]
