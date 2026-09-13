from lib.anime.episode_map import build_index, match_coordinates, resolve_episode
from lib.anime.providers import anizip as anizip_provider

# Real shape of the AniZip ``episodes`` mapping: keys are episode-number strings,
# values carry TVDB numbering plus the original air date.
SINGLE_SEASON = {
    "1": {
        "tvdbShowId": 267440,
        "tvdbId": 4516067,
        "seasonNumber": 1,
        "episodeNumber": 1,
        "absoluteEpisodeNumber": 1,
        "title": "Spring",
        "airDate": "2013-04-07",
        "airDateUtc": "2013-04-07T15:30:00Z",
        "runtime": 26,
        "episode": "1",
    },
    "2": {
        "tvdbShowId": 267440,
        "tvdbId": 4516068,
        "seasonNumber": 1,
        "episodeNumber": 2,
        "absoluteEpisodeNumber": 2,
        "title": "Summer",
        "airDate": "2013-04-14",
        "airDateUtc": "2013-04-14T15:30:00Z",
        "runtime": 26,
        "episode": "2",
    },
}

TWO_SEASONS = {
    "1": {
        "tvdbShowId": 267440,
        "tvdbId": 4516067,
        "seasonNumber": 1,
        "episodeNumber": 1,
        "absoluteEpisodeNumber": 1,
        "title": "First",
        "airDate": "2013-04-07",
    },
    "2": {
        "tvdbShowId": 267440,
        "tvdbId": 4516068,
        "seasonNumber": 2,
        "episodeNumber": 2,
        "absoluteEpisodeNumber": 2,
        "title": "Second",
        "airDate": "2013-04-14",
    },
}


def _fail(*args, **kwargs):
    raise AssertionError("unexpected provider call")


def _payload(episodes):
    return lambda anilist_id=None, mal_id=None: {"episodes": episodes}


# ── build_index ──────────────────────────────────────────────


def test_build_index_returns_empty_for_garbage_input():
    assert build_index(None) == []
    assert build_index("garbage") == []
    assert build_index(42) == []
    assert build_index([]) == []
    assert build_index({"1": None, "2": "garbage", "3": [1, 2]}) == []


def test_build_index_skips_entries_without_any_number():
    entries = {"bad": {"title": "Unusable key"}}

    assert build_index(entries) == []


def test_build_index_maps_payload_fields():
    index = build_index(SINGLE_SEASON)

    first = index[0]
    assert first.absolute == 1
    assert first.season == 1
    assert first.episode == 1
    assert first.tvdb_id == 4516067
    assert first.title == "Spring"
    assert first.air_date == "2013-04-07"
    assert first.matched_by is None


def test_build_index_sorts_by_absolute_episode_number():
    entries = {
        "1": {"seasonNumber": 1, "episodeNumber": 1, "absoluteEpisodeNumber": 30},
        "2": {"seasonNumber": 1, "episodeNumber": 2, "absoluteEpisodeNumber": 10},
        "3": {"seasonNumber": 1, "episodeNumber": 3, "absoluteEpisodeNumber": 20},
    }

    index = build_index(entries)

    assert [entry.absolute for entry in index] == [10, 20, 30]


def test_build_index_falls_back_to_episode_number_for_ordering():
    entries = {
        "1": {"seasonNumber": 1, "episodeNumber": 9},
        "2": {"seasonNumber": 1, "episodeNumber": 4},
    }

    index = build_index(entries)

    assert [entry.episode for entry in index] == [4, 9]


def test_build_index_falls_back_to_key_number_for_ordering():
    entries = {
        "2": {"title": "Second"},
        "1": {"title": "First"},
    }

    index = build_index(entries)

    assert [entry.title for entry in index] == ["First", "Second"]
    assert index[0].absolute is None


def test_build_index_coerces_string_numbers():
    entries = {
        "1": {
            "seasonNumber": "1",
            "episodeNumber": "2",
            "absoluteEpisodeNumber": "7",
            "tvdbId": "4516067",
        }
    }

    index = build_index(entries)

    assert index[0].absolute == 7
    assert index[0].season == 1
    assert index[0].episode == 2
    assert index[0].tvdb_id == 4516067


def test_build_index_normalizes_air_date():
    entries = {
        "1": {"episodeNumber": 1, "airDate": "2013-04-07"},
        "2": {"episodeNumber": 2, "airDate": "2013-04-07T12:30:00Z"},
        "3": {"episodeNumber": 3, "airDate": "not-a-date"},
        "4": {"episodeNumber": 4},
        "5": {"episodeNumber": 5, "airDate": " 2013-13-40 "},
    }

    index = build_index(entries)

    assert [entry.air_date for entry in index] == [
        "2013-04-07",
        "2013-04-07",
        None,
        None,
        None,
    ]


# ── match_coordinates ────────────────────────────────────────


def test_match_prefers_air_date_over_season_episode():
    index = build_index(TWO_SEASONS)

    result = match_coordinates(index, 2, 2, air_date="2013-04-07")

    assert result is not None
    assert result.absolute == 1
    assert result.matched_by == "air_date"


def test_match_uses_season_episode_without_air_date():
    index = build_index(TWO_SEASONS)

    result = match_coordinates(index, 2, 2)

    assert result is not None
    assert result.absolute == 2
    assert result.matched_by == "season_episode"


def test_match_coerces_string_coordinates_and_ignores_empty_air_date():
    index = build_index(TWO_SEASONS)

    result = match_coordinates(index, "2", "2", air_date="")

    assert result is not None
    assert result.absolute == 2
    assert result.matched_by == "season_episode"


def test_match_ignores_an_unusable_air_date():
    index = build_index(TWO_SEASONS)

    result = match_coordinates(index, 1, 1, air_date="04/07/2013")

    assert result is not None
    assert result.matched_by == "season_episode"


def test_match_positional_fallback_for_single_season_index():
    index = build_index(
        {
            "1": {"seasonNumber": 1, "episodeNumber": 11, "absoluteEpisodeNumber": 11},
            "2": {"seasonNumber": 1, "episodeNumber": 12, "absoluteEpisodeNumber": 12},
            "3": {"seasonNumber": 1, "episodeNumber": 13, "absoluteEpisodeNumber": 13},
        }
    )

    result = match_coordinates(index, 1, 2)

    assert result is not None
    assert result.absolute == 12
    assert result.episode == 12
    assert result.matched_by == "position"


def test_match_skips_positional_fallback_for_multi_season_index():
    index = build_index(TWO_SEASONS)

    assert match_coordinates(index, 3, 1) is None
    assert match_coordinates(index, 3, 2) is None


def test_match_skips_positional_fallback_out_of_range():
    index = build_index(SINGLE_SEASON)

    assert match_coordinates(index, 9, 0) is None
    assert match_coordinates(index, 9, 3) is None


def test_match_returns_none_for_unknown_coordinates():
    index = build_index(TWO_SEASONS)

    assert match_coordinates(index, 9, 9) is None
    assert match_coordinates(index, None, None) is None


def test_match_returns_none_for_empty_index():
    assert match_coordinates([], 1, 1) is None
    assert match_coordinates(None, 1, 1, air_date="2013-04-07") is None


def test_match_never_raises_for_garbage_input():
    assert match_coordinates("garbage", 1, 1) is None
    assert match_coordinates(42, 1, 1) is None
    assert match_coordinates({"1": {"episodeNumber": 1}}, 1, 1) is None
    assert match_coordinates([None, "x"], 1, 1) is None
    assert match_coordinates([object()], 1, 1, air_date=object()) is None


def test_match_does_not_mutate_the_index():
    index = build_index(TWO_SEASONS)

    first = match_coordinates(index, 1, 1)
    second = match_coordinates(index, 2, 2, air_date="2013-04-14")

    assert first is not None
    assert second is not None
    assert [entry.matched_by for entry in index] == [None, None]


# ── resolve_episode ──────────────────────────────────────────


def test_resolve_episode_returns_none_without_ids_and_skips_provider(monkeypatch):
    monkeypatch.setattr(anizip_provider, "mappings", _fail)

    assert resolve_episode(None, 1, 1) is None
    assert resolve_episode({}, 1, 1) is None
    assert resolve_episode({"tvdb_id": 1}, 1, 1) is None
    assert resolve_episode("garbage", 1, 1) is None


def test_resolve_episode_returns_none_when_provider_returns_none(monkeypatch):
    monkeypatch.setattr(anizip_provider, "mappings", lambda anilist_id=None, mal_id=None: None)

    assert resolve_episode({"anilist_id": 16498}, 1, 1) is None


def test_resolve_episode_returns_none_for_malformed_payload(monkeypatch):
    monkeypatch.setattr(anizip_provider, "mappings", lambda **kwargs: "garbage")

    assert resolve_episode({"mal_id": 1735}, 1, 1) is None


def test_resolve_episode_returns_none_without_episodes(monkeypatch):
    monkeypatch.setattr(
        anizip_provider,
        "mappings",
        lambda anilist_id=None, mal_id=None: {"mappings": {"anilist_id": 16498}, "episodes": {}},
    )

    assert resolve_episode({"anilist_id": 16498}, 1, 1) is None


def test_resolve_episode_returns_none_when_nothing_matches(monkeypatch):
    monkeypatch.setattr(anizip_provider, "mappings", _payload(TWO_SEASONS))

    assert resolve_episode({"anilist_id": 16498}, 9, 9) is None


def test_resolve_episode_never_raises_when_provider_raises(monkeypatch):
    def boom(anilist_id=None, mal_id=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(anizip_provider, "mappings", boom)

    assert resolve_episode({"anilist_id": 16498}, 1, 1) is None


def test_resolve_episode_forwards_ids_and_matches_payload(monkeypatch):
    calls = []

    def mappings(anilist_id=None, mal_id=None):
        calls.append((anilist_id, mal_id))
        return {"episodes": TWO_SEASONS}

    monkeypatch.setattr(anizip_provider, "mappings", mappings)

    result = resolve_episode({"anilist_id": "16498"}, 2, 2)

    assert calls == [(16498, None)]
    assert result is not None
    assert result.absolute == 2
    assert result.season == 2
    assert result.episode == 2
    assert result.matched_by == "season_episode"


def test_resolve_episode_uses_mal_id_when_anilist_id_missing(monkeypatch):
    calls = []

    def mappings(anilist_id=None, mal_id=None):
        calls.append((anilist_id, mal_id))
        return {"episodes": TWO_SEASONS}

    monkeypatch.setattr(anizip_provider, "mappings", mappings)

    result = resolve_episode({"mal_id": 1735, "anilist_id": ""}, 1, 1, air_date="2013-04-07")

    assert calls == [(None, 1735)]
    assert result is not None
    assert result.absolute == 1
    assert result.matched_by == "air_date"
