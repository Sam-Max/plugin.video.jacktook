from lib.anime.normalize import (
    ENGLISH,
    ROMAJI,
    AnimeRecord,
    pick_display_title,
    record_from_payloads,
)


def test_pick_display_title_prefers_requested_language():
    record = AnimeRecord(title_en="English Title", title_romaji="Romaji Title")

    assert pick_display_title(record, ENGLISH) == "English Title"
    assert pick_display_title(record, ROMAJI) == "Romaji Title"


def test_pick_display_title_falls_back_to_other_language():
    record = AnimeRecord(title_romaji="Romaji Title")

    assert pick_display_title(record, ENGLISH) == "Romaji Title"


def test_pick_display_title_falls_back_to_native():
    record = AnimeRecord(title_native="ナルト")

    assert pick_display_title(record, ENGLISH) == "ナルト"
    assert pick_display_title(record, ROMAJI) == "ナルト"


def test_pick_display_title_falls_back_to_default():
    record = AnimeRecord(title_default="Default Title")

    assert pick_display_title(record, ENGLISH) == "Default Title"


def test_pick_display_title_ignores_blank_values():
    record = AnimeRecord(title_en="  ", title_romaji="")

    assert pick_display_title(record, ENGLISH) is None


def test_pick_display_title_returns_none_without_titles():
    assert pick_display_title(AnimeRecord(), ENGLISH) is None


def test_pick_display_title_treats_unknown_language_as_english():
    record = AnimeRecord(title_en="English Title", title_romaji="Romaji Title")

    assert pick_display_title(record, 99) == "English Title"


def test_record_from_payloads_merges_with_precedence():
    anilist = {
        "id": 1,
        "idMal": 2,
        "title": {"english": "EN", "romaji": "ROM", "native": "NAT"},
        "synonyms": ["Alt", ""],
        "format": "TV",
        "status": "FINISHED",
        "episodes": 12,
        "description": "Desc",
        "coverImage": {"large": "cover.jpg"},
        "bannerImage": "banner.jpg",
        "startDate": {"year": 2020},
    }
    simkl = {"simkl": 10, "mal": 99, "anilist": 99, "tmdb": 5, "tvdb": 6, "imdb": "tt1"}
    anizip = {
        "anilist_id": 99,
        "tmdb_id": 7,
        "tvdb_id": 8,
        "thetvdb_id": 9,
        "imdb_id": "tt2",
    }
    seed = {"mal_id": 3, "tmdb_id": 4}

    record = record_from_payloads(anilist=anilist, simkl=simkl, anizip=anizip, seed=seed)

    assert record.anilist_id == 1
    assert record.mal_id == 2
    assert record.simkl_id == 10
    assert record.tmdb_id == 5
    assert record.tvdb_id == 6
    assert record.imdb_id == "tt1"
    assert record.title_en == "EN"
    assert record.title_romaji == "ROM"
    assert record.title_native == "NAT"
    assert record.title_default == "EN"
    assert record.episodes == 12
    assert record.format == "TV"
    assert record.status == "FINISHED"
    assert record.year == 2020
    assert record.description == "Desc"
    assert record.cover == "cover.jpg"
    assert record.banner == "banner.jpg"
    assert record.synonyms == ["Alt"]


def test_record_from_payloads_falls_back_to_seed_ids():
    record = record_from_payloads(seed={"anilist_id": 42, "tvdb_id": 7, "imdb_id": "tt9"})

    assert record.anilist_id == 42
    assert record.tvdb_id == 7
    assert record.imdb_id == "tt9"
    assert record.synonyms == []


def test_record_from_payloads_reads_nested_simkl_ids():
    simkl = {"ids": {"mal": 5, "anilist": 6, "anidb": 7, "kitsu": 8, "tmdb": 9, "imdb": "tt3"}}

    record = record_from_payloads(simkl=simkl)

    assert record.mal_id == 5
    assert record.anilist_id == 6
    assert record.anidb_id == 7
    assert record.kitsu_id == 8
    assert record.tmdb_id == 9
    assert record.imdb_id == "tt3"


def test_record_from_payloads_handles_missing_and_malformed_input():
    record = record_from_payloads(anilist=None, simkl="bad", anizip=[], seed=None)

    assert isinstance(record, AnimeRecord)
    assert record.anilist_id is None
    assert record.title_en is None
    assert record.synonyms == []
