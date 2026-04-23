from unittest.mock import patch

from lib.api.tmdbv3api.as_obj import AsObj
from lib.domain.torrent import TorrentStream
from lib.search import (
    _build_title_fallback_queries,
    _perform_search_with_title_fallback,
    SearchVariant,
    TITLE_LANGUAGE_ENGLISH_FIRST,
    TITLE_LANGUAGE_ENGLISH_ONLY,
    TITLE_LANGUAGE_LOCALIZED_FIRST,
)


def test_search_variant_enum_values():
    if not hasattr(SearchVariant, '__members__'):
        return
    assert SearchVariant.DEFAULT.value == "default"
    assert SearchVariant.TITLE_YEAR.value == "title_year"
    assert SearchVariant.ORIGINAL_TITLE.value == "original_title"
    assert SearchVariant.ORIGINAL_TITLE_YEAR.value == "original_title_year"


def test_build_title_fallback_queries_default_variant_uses_fallback_behavior():
    details = AsObj(
        {
            "original_title": "The Intouchables",
            "translations": {
                "translations": [
                    {"iso_639_1": "en", "data": {"title": "The Intouchables"}},
                ]
            },
        }
    )

    with patch(
        "lib.clients.tmdb.utils.utils.get_tmdb_media_details", return_value=details
    ):
        queries = _build_title_fallback_queries(
            "Intocable",
            {"tmdb_id": "77338"},
            "movies",
            variant=SearchVariant.DEFAULT,
        )

    assert "Intocable" in queries
    assert "The Intouchables" in queries


def test_build_title_fallback_queries_title_year_appends_year():
    queries = _build_title_fallback_queries(
        "Inception",
        {"tmdb_id": "27205"},
        "movies",
        variant=SearchVariant.TITLE_YEAR,
        year=2010,
    )

    assert queries == ["Inception 2010"]


def test_build_title_fallback_queries_original_title_uses_tmdb_original():
    details = AsObj(
        {
            "original_title": "千と千尋の神隠し",
            "translations": {
                "translations": [
                    {"iso_639_1": "en", "data": {"title": "Spirited Away"}},
                ]
            },
        }
    )

    with patch(
        "lib.clients.tmdb.utils.utils.get_tmdb_media_details", return_value=details
    ):
        queries = _build_title_fallback_queries(
            "Spirited Away",
            {"tmdb_id": "129"},
            "movies",
            variant=SearchVariant.ORIGINAL_TITLE,
        )

    assert queries == ["千と千尋の神隠し"]


def test_build_title_fallback_queries_original_title_year_appends_year():
    details = AsObj(
        {
            "original_title": "千と千尋の神隠し",
            "translations": {
                "translations": [
                    {"iso_639_1": "en", "data": {"title": "Spirited Away"}},
                ]
            },
        }
    )

    with patch(
        "lib.clients.tmdb.utils.utils.get_tmdb_media_details", return_value=details
    ):
        queries = _build_title_fallback_queries(
            "Spirited Away",
            {"tmdb_id": "129"},
            "movies",
            variant=SearchVariant.ORIGINAL_TITLE_YEAR,
            year=2001,
        )

    assert queries == ["千と千尋の神隠し 2001"]


def test_build_title_fallback_queries_title_year_without_ids():
    queries = _build_title_fallback_queries(
        "Inception",
        {},
        "movies",
        variant=SearchVariant.TITLE_YEAR,
        year=2010,
    )

    assert queries == ["Inception 2010"]


def test_build_title_fallback_queries_original_title_fallbacks_to_query():
    details = AsObj(
        {
            "original_title": "",
            "translations": {
                "translations": [
                    {"iso_639_1": "en", "data": {"title": "Some Movie"}},
                ]
            },
        }
    )

    with patch(
        "lib.clients.tmdb.utils.utils.get_tmdb_media_details", return_value=details
    ):
        queries = _build_title_fallback_queries(
            "Some Movie",
            {"tmdb_id": "123"},
            "movies",
            variant=SearchVariant.ORIGINAL_TITLE,
        )

    assert queries == ["Some Movie"]


def test_build_title_fallback_queries_prefers_english_translation_for_movies():
    details = AsObj(
        {
            "original_title": "The Intouchables",
            "translations": {
                "translations": [
                    {"iso_639_1": "es", "data": {"title": "Intocable"}},
                    {
                        "iso_639_1": "en",
                        "data": {"title": "The Intouchables"},
                    },
                ]
            },
        }
    )

    with patch(
        "lib.clients.tmdb.utils.utils.get_tmdb_media_details", return_value=details
    ):
        queries = _build_title_fallback_queries(
            "Intocable",
            {"tmdb_id": "77338"},
            "movies",
            title_language_mode=TITLE_LANGUAGE_LOCALIZED_FIRST,
        )

    assert queries == ["Intocable", "The Intouchables"]


def test_build_title_fallback_queries_english_first_reorders_candidates():
    details = AsObj(
        {
            "original_title": "The Intouchables",
            "translations": {
                "translations": [
                    {"iso_639_1": "es", "data": {"title": "Intocable"}},
                    {
                        "iso_639_1": "en",
                        "data": {"title": "The Intouchables"},
                    },
                ]
            },
        }
    )

    with patch(
        "lib.clients.tmdb.utils.utils.get_tmdb_media_details", return_value=details
    ):
        queries = _build_title_fallback_queries(
            "Intocable",
            {"tmdb_id": "77338"},
            "movies",
            title_language_mode=TITLE_LANGUAGE_ENGLISH_FIRST,
        )

    assert queries == ["The Intouchables", "Intocable"]


def test_build_title_fallback_queries_english_first_falls_back_to_original_before_localized():
    details = AsObj(
        {
            "original_title": "Avatar: Fire and Ash",
            "translations": {
                "translations": [
                    {"iso_639_1": "es", "data": {"title": "Avatar: Fuego y ceniza"}},
                ]
            },
        }
    )

    with patch(
        "lib.clients.tmdb.utils.utils.get_tmdb_media_details", return_value=details
    ):
        queries = _build_title_fallback_queries(
            "Avatar: Fuego y ceniza",
            {"tmdb_id": "123456"},
            "movies",
            title_language_mode=TITLE_LANGUAGE_ENGLISH_FIRST,
        )

    assert queries == ["Avatar: Fire and Ash", "Avatar: Fuego y ceniza"]


def test_build_title_fallback_queries_english_only_skips_localized_query():
    details = AsObj(
        {
            "original_title": "The Intouchables",
            "translations": {
                "translations": [
                    {"iso_639_1": "es", "data": {"title": "Intocable"}},
                    {
                        "iso_639_1": "en",
                        "data": {"title": "The Intouchables"},
                    },
                ]
            },
        }
    )

    with patch(
        "lib.clients.tmdb.utils.utils.get_tmdb_media_details", return_value=details
    ):
        queries = _build_title_fallback_queries(
            "Intocable",
            {"tmdb_id": "77338"},
            "movies",
            title_language_mode=TITLE_LANGUAGE_ENGLISH_ONLY,
        )

    assert queries == ["The Intouchables"]


def test_build_title_fallback_queries_uses_original_name_when_needed_for_tv():
    details = AsObj(
        {
            "original_name": "Shingeki no Kyojin",
            "translations": {
                "translations": [
                    {"iso_639_1": "de", "data": {"name": "Attack on Titan"}},
                    {
                        "iso_639_1": "en",
                        "data": {"name": "Attack on Titan"},
                    },
                ]
            },
        }
    )

    with patch(
        "lib.clients.tmdb.utils.utils.get_tmdb_media_details", return_value=details
    ):
        queries = _build_title_fallback_queries(
            "Ataque a los Titanes", {"tmdb_id": "1429"}, "tv"
        )

    assert queries == [
        "Ataque a los Titanes",
        "Attack on Titan",
        "Shingeki no Kyojin",
    ]


def test_perform_search_with_title_fallback_retries_until_results_found():
    expected = [TorrentStream(title="The Intouchables 2011")]

    with patch(
        "lib.search._build_title_fallback_queries",
        return_value=["Intocable", "The Intouchables", "Untouchables"],
    ), patch(
        "lib.search._perform_search",
        side_effect=[[], expected],
    ) as mock_search:
        results = _perform_search_with_title_fallback(
            "Prowlarr", None, "Intocable", {"tmdb_id": "77338"}, "movies", None, None
        )

    assert results == expected
    assert mock_search.call_count == 2
    assert mock_search.call_args_list[0].args == (
        "Prowlarr",
        None,
        "Intocable",
        "movies",
        None,
        None,
    )
    assert mock_search.call_args_list[1].args == (
        "Prowlarr",
        None,
        "The Intouchables",
        "movies",
        None,
        None,
    )
