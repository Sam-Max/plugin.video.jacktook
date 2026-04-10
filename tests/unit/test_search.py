from unittest.mock import patch

from lib.api.tmdbv3api.as_obj import AsObj
from lib.search import SearchVariant, _build_title_fallback_queries, show_source_select


def test_search_variant_values():
    assert SearchVariant.DEFAULT == "default"
    assert SearchVariant.TITLE_YEAR == "title_year"
    assert SearchVariant.ORIGINAL_TITLE == "original_title"
    assert SearchVariant.ORIGINAL_TITLE_YEAR == "original_title_year"


def test_build_title_fallback_queries_default_variant_uses_tmdb_titles():
    details = AsObj(
        {
            "original_name": "Shingeki no Kyojin",
            "translations": {
                "translations": [
                    {"iso_639_1": "en", "data": {"name": "Attack on Titan"}},
                ]
            },
        }
    )

    with patch(
        "lib.clients.tmdb.utils.utils.get_tmdb_media_details", return_value=details
    ):
        queries = _build_title_fallback_queries(
            "Ataque a los Titanes",
            {"tmdb_id": "1429"},
            "tv",
        )

    assert queries == ["Ataque a los Titanes", "Attack on Titan", "Shingeki no Kyojin"]


def test_build_title_fallback_queries_supports_variants_and_year():
    details = AsObj(
        {
            "original_name": "Shingeki no Kyojin",
            "translations": {
                "translations": [
                    {"iso_639_1": "en", "data": {"name": "Attack on Titan"}},
                ]
            },
        }
    )

    with patch(
        "lib.clients.tmdb.utils.utils.get_tmdb_media_details", return_value=details
    ):
        title_year_queries = _build_title_fallback_queries(
            "Ataque a los Titanes",
            {"tmdb_id": "1429"},
            "tv",
            variant=SearchVariant.TITLE_YEAR,
            year=2013,
        )
        original_title_queries = _build_title_fallback_queries(
            "Ataque a los Titanes",
            {"tmdb_id": "1429"},
            "tv",
            variant=SearchVariant.ORIGINAL_TITLE,
        )
        original_title_year_queries = _build_title_fallback_queries(
            "Ataque a los Titanes",
            {"tmdb_id": "1429"},
            "tv",
            variant=SearchVariant.ORIGINAL_TITLE_YEAR,
            year=2013,
        )

    assert title_year_queries == ["Ataque a los Titanes 2013"]
    assert original_title_queries == ["Shingeki no Kyojin"]
    assert original_title_year_queries == ["Shingeki no Kyojin 2013"]


def test_show_source_select_passes_year_from_media_metadata():
    results = [object()]
    metadata = {"year": 2010, "title": "Inception", "original_title": "Inception"}

    with patch("lib.search.build_media_metadata", return_value=metadata), patch(
        "lib.search.source_select", return_value=True
    ) as source_select_mock:
        show_source_select(
            results,
            "movies",
            {"tmdb_id": "27205"},
            {},
            "Inception",
            "movie",
            False,
        )

    item_info = source_select_mock.call_args[0][0]
    assert item_info["year"] == 2010
    assert item_info["query"] == "Inception"
