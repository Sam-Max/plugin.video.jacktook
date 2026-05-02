import json
from unittest.mock import MagicMock, patch

import pytest

from lib.api.tmdbv3api.as_obj import AsObj
from lib.search import (
    SearchVariant,
    _build_title_fallback_queries,
    _is_source_enabled,
    show_source_select,
)
from lib.utils.general.utils import Indexer


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

    assert title_year_queries == [
        "Ataque a los Titanes 2013",
        "Attack on Titan 2013",
        "Shingeki no Kyojin 2013",
    ]
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


def test_is_source_enabled_returns_true_when_cache_empty():
    with patch("lib.search.cache") as mock_cache:
        mock_cache.get.return_value = None
        assert _is_source_enabled(Indexer.JACKETT) is True
        assert _is_source_enabled(Indexer.STREMIO, "some_addon") is True


def test_is_source_enabled_returns_true_when_cache_invalid():
    with patch("lib.search.cache") as mock_cache:
        mock_cache.get.return_value = "not-json"
        assert _is_source_enabled(Indexer.JACKETT) is True


@patch("lib.search.get_setting")
def test_is_source_enabled_checks_builtin_by_indexer_name(mock_get_setting):
    def setting_side_effect(key):
        return key in ("jackett_enabled", "prowlarr_enabled")

    mock_get_setting.side_effect = setting_side_effect
    with patch("lib.search.cache") as mock_cache:
        mock_cache.get.return_value = json.dumps(["Jackett", "Prowlarr"])
        assert _is_source_enabled(Indexer.JACKETT) is True
        assert _is_source_enabled(Indexer.BURST) is False
        assert _is_source_enabled(Indexer.PROWLARR) is True


def test_is_source_enabled_checks_stremio_addon_key():
    with patch("lib.search.cache") as mock_cache:
        mock_cache.get.return_value = json.dumps(["Stremio:addon1|url1", "Jackett"])
        assert _is_source_enabled(Indexer.STREMIO, "addon1|url1") is True
        assert _is_source_enabled(Indexer.STREMIO, "addon2|url2") is False


@patch("lib.search.get_setting")
@patch("lib.search.cache")
@patch("lib.search._perform_search_with_title_fallback")
@patch("lib.search._perform_search")
def test_submit_search_tasks_skips_disabled_sources(
    mock_perform_search,
    mock_perform_fallback,
    mock_cache,
    mock_get_setting,
):
    def setting_side_effect(key):
        if key == "jackett_enabled":
            return True
        return False

    mock_get_setting.side_effect = setting_side_effect
    mock_cache.get.return_value = json.dumps(["Jackett"])
    executor = MagicMock()
    tasks = []
    dialog = MagicMock()

    from lib.search import _submit_search_tasks

    _submit_search_tasks(
        executor,
        tasks,
        dialog,
        "query",
        "movies",
        "movie",
        1,
        1,
        {"imdb_id": "tt123"},
        "",
        "123",
        "tt123",
        True,
    )

    # Only Jackett task should be added.
    # Burst/Prowlarr/Jackgram/Easynews/Stremio/ExternalScraper are disabled.
    assert executor.submit.call_count == 1


@patch("lib.search.get_setting")
@patch("lib.search.cache")
@patch("lib.search.get_selected_stream_addons")
def test_submit_search_tasks_managed_filters_stremio_addons(
    mock_get_addons,
    mock_cache,
    mock_get_setting,
):
    mock_get_setting.return_value = True
    mock_cache.get.return_value = json.dumps(["Stremio:addon1|url1"])

    addon1 = MagicMock()
    addon1.key.return_value = "addon1|url1"
    addon1.manifest.name = "Addon One"
    addon1.url.return_value = "http://a.com"

    addon2 = MagicMock()
    addon2.key.return_value = "addon2|url2"
    addon2.manifest.name = "Addon Two"
    addon2.url.return_value = "http://b.com"

    mock_get_addons.return_value = [addon1, addon2]

    manager = MagicMock()
    dialog = MagicMock()

    from lib.search import _submit_search_tasks_managed

    _submit_search_tasks_managed(
        manager,
        dialog,
        "query",
        "tv",
        "tv",
        1,
        1,
        {"imdb_id": "tt123"},
        "",
        "123",
        "tt123",
    )

    # Only addon1 should be submitted
    stremio_calls = [
        call
        for call in manager.submit_task.call_args_list
        if call[0][1] == Indexer.STREMIO
    ]
    assert len(stremio_calls) == 1
    assert stremio_calls[0][1]["scoped_addon_url"] == "http://a.com"
