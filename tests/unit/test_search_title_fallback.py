from unittest.mock import patch

from lib.api.tmdbv3api.as_obj import AsObj
from lib.domain.torrent import TorrentStream
from lib.search import _build_title_fallback_queries, _perform_search_with_title_fallback


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
            "Intocable", {"tmdb_id": "77338"}, "movies"
        )

    assert queries == ["Intocable", "The Intouchables"]


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
