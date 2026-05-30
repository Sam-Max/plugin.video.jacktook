import json
from unittest.mock import MagicMock, patch

from lib.api.tmdbv3api.as_obj import AsObj
from lib.search import (
    SearchVariant,
    _build_title_fallback_queries,
    _check_search_caches,
    _is_source_enabled,
    run_search_entry,
    search_client,
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

    with patch("lib.clients.tmdb.utils.utils.get_tmdb_media_details", return_value=details):
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

    with patch("lib.clients.tmdb.utils.utils.get_tmdb_media_details", return_value=details):
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


def test_show_source_select_playnext_context_sets_direct_without_autoplay():
    results = [object()]

    with patch("lib.search.build_media_metadata", return_value={}), patch(
        "lib.search.source_select", return_value=True
    ) as source_select_mock:
        show_source_select(
            results,
            "tv",
            {"tmdb_id": "123"},
            {"season": 1, "episode": 2},
            "Show",
            "tv",
            False,
            autoplay_context="1",
        )

    item_info = source_select_mock.call_args[0][0]
    assert item_info["playnext_context"] is True
    assert item_info["direct_play"] is True
    assert "autoplay" not in item_info


def test_run_search_entry_source_select_cancel_skipped_on_back():
    params = {
        "query": "Show",
        "mode": "tv",
        "media_type": "tv",
        "ids": json.dumps({"tmdb_id": "123"}),
        "tv_data": json.dumps({"season": 1, "episode": 2}),
        "skip_cancel_on_back": True,
    }

    with patch("lib.search._handle_super_quick_play", return_value=False), patch(
        "lib.search.search_client", return_value=[object()]
    ), patch(
        "lib.search._process_search_results", return_value=[object()]
    ), patch("lib.search.set_content_type"), patch(
        "lib.search.set_watched_title"
    ), patch("lib.search.auto_play_enabled", return_value=False), patch(
        "lib.search.show_source_select", return_value=False
    ), patch("lib.search.cancel_playback") as cancel_mock:
        run_search_entry(params)

    cancel_mock.assert_not_called()


def test_run_search_entry_source_select_cancel_on_back_when_not_skipped():
    params = {
        "query": "Show",
        "mode": "tv",
        "media_type": "tv",
        "ids": json.dumps({"tmdb_id": "123"}),
        "tv_data": json.dumps({"season": 1, "episode": 2}),
        "skip_cancel_on_back": False,
    }

    with patch("lib.search._handle_super_quick_play", return_value=False), patch(
        "lib.search.search_client", return_value=[object()]
    ), patch(
        "lib.search._process_search_results", return_value=[object()]
    ), patch("lib.search.set_content_type"), patch(
        "lib.search.set_watched_title"
    ), patch("lib.search.auto_play_enabled", return_value=False), patch(
        "lib.search.show_source_select", return_value=False
    ), patch("lib.search.cancel_playback") as cancel_mock:
        run_search_entry(params)

    cancel_mock.assert_called_once_with()


def test_run_search_entry_passes_decoded_episode_name_to_result_processing():
    params = {
        "query": "Show",
        "mode": "tv",
        "media_type": "tv",
        "ids": json.dumps({"tmdb_id": "123"}),
        "tv_data": json.dumps(
            {
                "name": "The%20Scales%20%26%20the%20Sword",
                "season": "2",
                "episode": "3",
            }
        ),
        "skip_cancel_on_back": True,
    }

    with patch("lib.search._handle_super_quick_play", return_value=False), patch(
        "lib.search.search_client", return_value=[object()]
    ), patch(
        "lib.search._process_search_results", return_value=[object()]
    ) as process_results_mock, patch("lib.search.set_content_type"), patch(
        "lib.search.set_watched_title"
    ), patch("lib.search.auto_play_enabled", return_value=False), patch(
        "lib.search.show_source_select", return_value=False
    ):
        run_search_entry(params)

    process_args = process_results_mock.call_args[0]
    assert process_args[2] == "The Scales & the Sword"
    assert process_args[3] == 3
    assert process_args[4] == 2


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
        call for call in manager.submit_task.call_args_list if call[0][1] == Indexer.STREMIO
    ]
    assert len(stremio_calls) == 1
    assert stremio_calls[0][1]["scoped_addon_url"] == "http://a.com"


# ---------------------------------------------------------------------------
# _check_search_caches
# ---------------------------------------------------------------------------


class TestCheckSearchCaches:
    """Cover all branches of _check_search_caches."""

    def test_standard_cache_hit_returns_results(self):
        """Standard cache hit returns cached results immediately (even empty list)."""
        cached = [MagicMock(), MagicMock()]
        with patch("lib.search.get_cached_results", return_value=cached):
            result = _check_search_caches("q", {}, "movies", "movie", 0, 0, "scope")
        assert result == cached

    def test_standard_cache_hit_empty_list_returns_empty(self):
        """Standard cache hit with ``[]`` returns empty list, not None."""
        with patch("lib.search.get_cached_results", return_value=[]):
            result = _check_search_caches("q", {}, "movies", "movie", 0, 0, "scope")
        assert result == []

    def test_cache_miss_non_tv_skips_autoscrape(self):
        """Standard cache miss + non-TV mode = no autoscrape fallback."""
        with patch("lib.search.get_cached_results", return_value=None):
            result = _check_search_caches("q", {}, "movies", "movie", 0, 0, "scope")
        assert result is None

    def test_cache_miss_tv_no_ids_skips_autoscrape(self):
        """TV mode but no id_value → skip autoscrape fallback."""
        with patch("lib.search.get_cached_results", return_value=None):
            result = _check_search_caches("q", {}, "tv", "tv", 0, 0, "scope")
        assert result is None

    def test_cache_miss_tv_no_autoscrape_data_returns_none(self):
        """Autoscrape key exists but cache miss → return None."""
        ids = {"tmdb_id": "123"}
        with (
            patch("lib.search.get_cached_results", return_value=None),
            patch("lib.db.cached.cache.get", return_value=None),
            patch("lib.utils.player.utils.get_autoscrape_results_cache_key", return_value="as:123_1_2"),
        ):
            result = _check_search_caches("q", ids, "tv", "tv", 2, 1, "scope")
        assert result is None

    def test_cache_miss_tv_autoscrape_hit_migrates_and_returns(self):
        """Autoscrape hit → migrate to standard cache + return results."""
        ids = {"imdb_id": "tt999"}
        autoscrape_results = [MagicMock(), MagicMock()]
        with (
            patch("lib.search.get_cached_results", return_value=None),
            patch("lib.db.cached.cache.get", return_value=autoscrape_results),
            patch("lib.utils.player.utils.get_autoscrape_results_cache_key", return_value="as:tt999_2_3"),
            patch("lib.search.cache_results") as mock_cache_results,
        ):
            result = _check_search_caches("q", ids, "tv", "tv", 3, 2, "scope")

        assert result == autoscrape_results
        mock_cache_results.assert_called_once_with(
            autoscrape_results, "q", "tv", "tv", 3, cache_scope="scope",
        )


# ---------------------------------------------------------------------------
# search_client  (orchestration)
# ---------------------------------------------------------------------------


class TestSearchClient:
    """Cover orchestration logic of search_client (branching, cache, search dispatch)."""

    def test_rescrape_skips_cache_checks(self):
        """rescrape=True → skip _check_search_caches entirely."""
        with (
            patch("lib.search.close_busy_dialog"),
            patch("lib.search._infer_tmdb_year", return_value=2020),
            patch("lib.search._build_title_fallback_queries", return_value=["q 2020"]),
            patch("lib.search._build_search_cache_scope", return_value="scope"),
            patch("lib.search._check_search_caches") as mock_check,
            patch("lib.search.get_setting", return_value="0"),
            patch("lib.search._run_simple_search", return_value=[]),
            patch("lib.search.cache_results"),
        ):
            search_client("q", {}, "movies", "movie", rescrape=True, season=0, episode=0)

        mock_check.assert_not_called()

    def test_not_rescrape_cache_hit_returns_early(self):
        """Not rescrape + cache hit → return cached, no search."""
        cached = [MagicMock()]
        with (
            patch("lib.search.close_busy_dialog"),
            patch("lib.search._infer_tmdb_year", return_value=2020),
            patch("lib.search._build_title_fallback_queries", return_value=["q 2020"]),
            patch("lib.search._build_search_cache_scope", return_value="scope"),
            patch("lib.search._check_search_caches", return_value=cached),
            patch("lib.search.get_setting") as mock_get_setting,
            patch("lib.search._run_simple_search") as mock_simple,
            patch("lib.search._run_detailed_search") as mock_detailed,
            patch("lib.search.cache_results") as mock_cache_results,
        ):
            result = search_client("q", {}, "movies", "movie", rescrape=False, season=0, episode=0)

        assert result == cached
        mock_simple.assert_not_called()
        mock_detailed.assert_not_called()
        mock_cache_results.assert_not_called()

    def test_cache_miss_detailed_dialog_branch(self):
        """Cache miss + search_dialog_style=1 → calls _run_detailed_search."""
        expected = [MagicMock()]
        with (
            patch("lib.search.close_busy_dialog"),
            patch("lib.search._infer_tmdb_year", return_value=2020),
            patch("lib.search._build_title_fallback_queries", return_value=["q 2020"]),
            patch("lib.search._build_search_cache_scope", return_value="scope"),
            patch("lib.search._check_search_caches", return_value=None),
            patch("lib.search.get_setting", return_value="1"),
            patch("lib.search._run_detailed_search", return_value=expected) as mock_detailed,
            patch("lib.search._run_simple_search") as mock_simple,
            patch("lib.search.cache_results") as mock_cache,
        ):
            result = search_client("q", {}, "movies", "movie", rescrape=False, season=0, episode=0)

        assert result == expected
        mock_detailed.assert_called_once()
        mock_simple.assert_not_called()
        mock_cache.assert_called_once()

    def test_cache_miss_simple_dialog_branch(self):
        """Cache miss + search_dialog_style=0 → calls _run_simple_search."""
        expected = [MagicMock()]
        with (
            patch("lib.search.close_busy_dialog"),
            patch("lib.search._infer_tmdb_year", return_value=2020),
            patch("lib.search._build_title_fallback_queries", return_value=["q 2020"]),
            patch("lib.search._build_search_cache_scope", return_value="scope"),
            patch("lib.search._check_search_caches", return_value=None),
            patch("lib.search.get_setting", return_value="0"),
            patch("lib.search._run_detailed_search") as mock_detailed,
            patch("lib.search._run_simple_search", return_value=expected) as mock_simple,
            patch("lib.search.cache_results"),
        ):
            result = search_client("q", {}, "movies", "movie", rescrape=False, season=0, episode=0)

        assert result == expected
        mock_simple.assert_called_once()
        mock_detailed.assert_not_called()

    def test_show_dialog_false_uses_simple_branch(self):
        """show_dialog=False → simple branch regardless of search_dialog_style."""
        expected = [MagicMock()]
        with (
            patch("lib.search.close_busy_dialog"),
            patch("lib.search._infer_tmdb_year", return_value=2020),
            patch("lib.search._build_title_fallback_queries", return_value=["q 2020"]),
            patch("lib.search._build_search_cache_scope", return_value="scope"),
            patch("lib.search._check_search_caches", return_value=None),
            patch("lib.search.get_setting", return_value="1"),  # would trigger detailed, but show_dialog=False
            patch("lib.search._run_detailed_search") as mock_detailed,
            patch("lib.search._run_simple_search", return_value=expected) as mock_simple,
            patch("lib.search.cache_results"),
        ):
            result = search_client(
                "q", {}, "movies", "movie", rescrape=False,
                season=0, episode=0, show_dialog=False,
            )

        assert result == expected
        mock_simple.assert_called_once()
        mock_detailed.assert_not_called()

    def test_passes_year_to_infer_when_none(self):
        """year=None → _infer_tmdb_year is called."""
        with (
            patch("lib.search.close_busy_dialog"),
            patch("lib.search._infer_tmdb_year", return_value=2020) as mock_infer,
            patch("lib.search._build_title_fallback_queries", return_value=["q"]),
            patch("lib.search._build_search_cache_scope", return_value="scope"),
            patch("lib.search._check_search_caches", return_value=None),
            patch("lib.search.get_setting", return_value="0"),
            patch("lib.search._run_simple_search", return_value=[]),
            patch("lib.search.cache_results"),
        ):
            search_client("q", {"tmdb_id": "123"}, "movies", "movie", rescrape=False, season=0, episode=0)

        mock_infer.assert_called_once_with({"tmdb_id": "123"}, "movies")

    def test_does_not_infer_year_when_provided(self):
        """year=2010 → _infer_tmdb_year is NOT called."""
        with (
            patch("lib.search.close_busy_dialog"),
            patch("lib.search._infer_tmdb_year") as mock_infer,
            patch("lib.search._build_title_fallback_queries", return_value=["q"]),
            patch("lib.search._build_search_cache_scope", return_value="scope"),
            patch("lib.search._check_search_caches", return_value=None),
            patch("lib.search.get_setting", return_value="0"),
            patch("lib.search._run_simple_search", return_value=[]),
            patch("lib.search.cache_results"),
        ):
            search_client("q", {}, "movies", "movie", rescrape=False, season=0, episode=0, year=2010)

        mock_infer.assert_not_called()
