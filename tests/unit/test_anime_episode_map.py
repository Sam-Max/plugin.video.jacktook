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


def test_match_rejects_positional_fallback_for_an_absent_season():
    index = build_index(SINGLE_SEASON)

    # Regression: the index only holds season 1, so a season 3 request must not be
    # answered by position. It must not surface the first entry of the index either.
    result = match_coordinates(index, 3, 1)

    assert result is not index[0]
    assert result is None


def test_match_rejects_positional_fallback_for_every_absent_season_episode():
    index = build_index(
        {
            "1": {"seasonNumber": 1, "episodeNumber": 1, "absoluteEpisodeNumber": 1},
            "2": {"seasonNumber": 1, "episodeNumber": 2, "absoluteEpisodeNumber": 2},
            "3": {"seasonNumber": 1, "episodeNumber": 3, "absoluteEpisodeNumber": 3},
        }
    )

    assert [match_coordinates(index, 3, episode) for episode in (1, 2, 3)] == [None, None, None]


def test_match_keeps_positional_fallback_for_a_present_requested_season():
    index = build_index(
        {
            "1": {"seasonNumber": 7, "episodeNumber": 11, "absoluteEpisodeNumber": 11},
            "2": {"seasonNumber": 7, "episodeNumber": 12, "absoluteEpisodeNumber": 12},
            "3": {"seasonNumber": 7, "episodeNumber": 13, "absoluteEpisodeNumber": 13},
        }
    )

    result = match_coordinates(index, 7, 2)

    assert result is not None
    assert result.absolute == 12
    assert result.episode == 12
    assert result.matched_by == "position"

    # The range guard still applies for a season the index actually holds.
    assert match_coordinates(index, 7, 0) is None
    assert match_coordinates(index, 7, 4) is None


def test_match_prefers_season_episode_over_position_when_both_could_apply():
    index = build_index(
        {
            "1": {"seasonNumber": 1, "episodeNumber": 1, "absoluteEpisodeNumber": 100},
            "2": {"seasonNumber": 1, "episodeNumber": 5, "absoluteEpisodeNumber": 200},
            "3": {"seasonNumber": 1, "episodeNumber": 9, "absoluteEpisodeNumber": 300},
        }
    )

    # Position 5 does not exist in a three-entry index, so only ``season_episode``
    # can answer this request: strategy order must stay air_date -> season_episode
    # -> position.
    result = match_coordinates(index, 1, 5)

    assert result is not None
    assert result.absolute == 200
    assert result.matched_by == "season_episode"


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


# ── AniZip's second entry shape (AniDB) ──────────────────────

# AniZip mixes two entry shapes in one ``episodes`` mapping. TVDB entries carry a
# season, an ``absoluteEpisodeNumber`` and a camelCase ``airDate``; AniDB entries
# carry no season at all, keep the number in the string ``episode`` field and the
# date in the lowercase ``airdate`` field. One Piece (kitsu 12) is the live case:
# TMDB asks for season 23 episode 1160, and the only entry carrying that episode's
# 2026-05-03 air date is AniDB-shaped.
ONE_PIECE = {
    "1": {
        "tvdbShowId": 81797,
        "tvdbId": 361887,
        "seasonNumber": 0,
        "episodeNumber": 1,
        "absoluteEpisodeNumber": 1,
        "title": "Special",
        "airDate": "1999-10-20",
        "episode": "1",
        "airdate": "1999-10-20",
    },
    "2": {
        "tvdbShowId": 81797,
        "tvdbId": 361888,
        "seasonNumber": 1,
        "episodeNumber": 1,
        "absoluteEpisodeNumber": 2,
        "title": "I'm Luffy!",
        "airDate": "1999-10-20",
        "episode": "2",
        "airdate": "1999-10-20",
    },
    "3": {
        "tvdbShowId": 81797,
        "tvdbId": 361889,
        "seasonNumber": 2,
        "episodeNumber": 1,
        "absoluteEpisodeNumber": 62,
        "title": "Episode of Arabasta",
        "airDate": "2001-01-10",
        "episode": "62",
        "airdate": "2001-01-10",
    },
    "1159": {
        "episode": "1159",
        "anidbEid": 306178,
        "length": 25,
        "airdate": "2026-04-26",
        "rating": "7.98",
        "title": {"en": "The Giant Warrior Pirates"},
    },
    "1160": {
        "episode": "1160",
        "anidbEid": 306179,
        "length": 25,
        "airdate": "2026-05-03",
        "rating": "8.22",
        "title": {"en": "An Encounter on a Snowfield - Loki, the Accursed Prince"},
    },
}


def test_build_index_indexes_an_anidb_shaped_entry():
    index = build_index(
        {
            "1160": {
                "episode": "1160",
                "airdate": "2026-05-03",
                "title": {"en": "An Encounter on a Snowfield"},
            }
        }
    )

    entry = index[0]
    assert entry.absolute == 1160
    assert entry.air_date == "2026-05-03"
    assert entry.season is None
    assert entry.episode is None


def test_build_index_keeps_the_tvdb_shaped_entry_unchanged():
    index = build_index(
        {
            "1": {
                "tvdbShowId": 81797,
                "tvdbId": 361887,
                "seasonNumber": 1,
                "episodeNumber": 1,
                "absoluteEpisodeNumber": 1,
                "title": "I'm Luffy!",
                "airDate": "1999-10-20",
                "episode": "1",
                "airdate": "1999-10-20",
            }
        }
    )

    entry = index[0]
    assert entry.absolute == 1
    assert entry.season == 1
    assert entry.episode == 1
    assert entry.tvdb_id == 361887
    assert entry.air_date == "1999-10-20"


def test_build_index_never_takes_a_tvdb_episode_number_as_absolute():
    index = build_index(
        {
            "1": {"seasonNumber": 1, "episodeNumber": 9, "episode": "9"},
            "2": {"seasonNumber": 2, "episodeNumber": 3, "absoluteEpisodeNumber": 30},
        }
    )

    assert [entry.absolute for entry in index] == [None, 30]
    assert [entry.episode for entry in index] == [9, 3]


def test_build_index_accepts_the_lowercase_airdate_field():
    index = build_index(
        {
            "1": {
                "seasonNumber": 1,
                "episodeNumber": 1,
                "absoluteEpisodeNumber": 1,
                "airdate": "2013-04-07",
            },
            "2": {
                "seasonNumber": 1,
                "episodeNumber": 2,
                "absoluteEpisodeNumber": 2,
                "airdate": "2013-04-07T12:30:00Z",
            },
        }
    )

    assert [entry.air_date for entry in index] == ["2013-04-07", "2013-04-07"]


def test_match_resolves_one_piece_season_23_through_the_anidb_air_date():
    index = build_index(ONE_PIECE)

    result = match_coordinates(index, 23, 1160, "2026-05-03")

    assert result is not None
    assert result.absolute == 1160
    assert result.matched_by == "air_date"


def test_match_returns_none_for_one_piece_without_an_air_date():
    index = build_index(ONE_PIECE)

    # Without the air date the request must stay unanswered: neither the season nor
    # the episode number exist in the index, and nothing may be fabricated.
    assert match_coordinates(index, 23, 1160, None) is None
    assert match_coordinates(index, 23, 1160) is None


def test_anidb_entries_do_not_widen_the_seasons_the_index_describes():
    index = build_index(ONE_PIECE)

    # AniDB entries carry no season, so they never join the TVDB season set that gates
    # the positional fallback: One Piece still describes exactly {0, 1, 2}.
    assert {entry.season for entry in index if entry.season is not None} == {0, 1, 2}
    assert [entry.absolute for entry in index] == [1, 2, 62, 1159, 1160]


def test_one_piece_index_still_refuses_the_positional_fallback():
    index = build_index(ONE_PIECE)

    # Regression pin for ce41862e: season 23 is absent from the index, so neither a
    # season/episode nor a positional answer may be fabricated for it, while the
    # seasons the index does describe still answer normally.
    assert match_coordinates(index, 23, 1) is None
    assert match_coordinates(index, 5, 1) is None

    answered = match_coordinates(index, 1, 1)
    assert answered is not None
    assert answered.matched_by == "season_episode"


def test_match_keeps_mushoku_tensei_season_3_unanswered():
    index = build_index(
        {
            "1": {"seasonNumber": 1, "episodeNumber": 1, "absoluteEpisodeNumber": 1},
            "2": {"seasonNumber": 1, "episodeNumber": 2, "absoluteEpisodeNumber": 2},
            "3": {"seasonNumber": 1, "episodeNumber": 3, "absoluteEpisodeNumber": 3},
            "4": {"seasonNumber": 1, "episodeNumber": 4, "absoluteEpisodeNumber": 4},
            "5": {"seasonNumber": 1, "episodeNumber": 5, "absoluteEpisodeNumber": 5},
            "6": {"seasonNumber": 1, "episodeNumber": 6, "absoluteEpisodeNumber": 6},
        }
    )

    assert match_coordinates(index, 3, 1) is None
    assert match_coordinates(index, 3, 6) is None


def test_match_keeps_mushoku_tensei_season_3_unanswered_with_anidb_entries():
    index = build_index(
        {
            "1": {"seasonNumber": 1, "episodeNumber": 1, "absoluteEpisodeNumber": 1},
            "2": {"seasonNumber": 1, "episodeNumber": 2, "absoluteEpisodeNumber": 2},
            "3": {"episode": "3", "airdate": "2021-01-10"},
            "4": {"episode": "4", "airdate": "2021-01-17"},
            "5": {"episode": "5", "airdate": "2021-01-24"},
            "6": {"episode": "6", "airdate": "2021-01-31"},
        }
    )

    # AniDB entries carry no season, so they must not open the positional fallback for
    # a season the index does not describe: the ce41862e guard still reads {1} here.
    assert match_coordinates(index, 3, 1) is None
    assert match_coordinates(index, 3, 6) is None

    # The same entries stay usable through the season the index does describe and
    # through the air date.
    assert match_coordinates(index, 1, 3) is not None
    dated = match_coordinates(index, 1, 3, "2021-01-10")
    assert dated is not None
    assert dated.absolute == 3
    assert dated.matched_by == "air_date"


def test_match_prefers_the_lowercase_airdate_over_season_episode():
    index = build_index(
        {
            "1": {
                "seasonNumber": 1,
                "episodeNumber": 1,
                "absoluteEpisodeNumber": 1,
                "airdate": "2013-04-07",
            },
            "2": {
                "seasonNumber": 2,
                "episodeNumber": 2,
                "absoluteEpisodeNumber": 2,
                "airdate": "2013-04-14",
            },
        }
    )

    result = match_coordinates(index, 2, 2, air_date="2013-04-07")

    assert result is not None
    assert result.absolute == 1
    assert result.matched_by == "air_date"


def test_resolve_episode_resolves_one_piece_through_anidb_entries(monkeypatch):
    monkeypatch.setattr(anizip_provider, "mappings", _payload(ONE_PIECE))

    result = resolve_episode({"anilist_id": 21, "mal_id": 21}, 23, 1160, "2026-05-03")

    assert result is not None
    assert result.absolute == 1160
    assert result.matched_by == "air_date"


def test_resolve_episode_returns_none_for_one_piece_without_an_air_date(monkeypatch):
    monkeypatch.setattr(anizip_provider, "mappings", _payload(ONE_PIECE))

    assert resolve_episode({"anilist_id": 21}, 23, 1160) is None
