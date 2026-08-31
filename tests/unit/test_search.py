import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from lib.api.tmdbv3api.as_obj import AsObj
from lib.clients.stremio.playback import StremioPlaybackError
from lib.domain.torrent import TorrentStream
from lib.search import (
    SearchCancelled,
    SearchVariant,
    _build_search_cache_scope,
    _build_title_fallback_queries,
    _check_search_caches,
    _handle_super_quick_play,
    _is_source_enabled,
    _submit_search_tasks,
    run_search_entry,
    search_client,
    show_source_select,
)
from lib.utils.general.utils import Indexer, IndexerType, Players


def test_search_variant_values():
    assert SearchVariant.DEFAULT == "default"
    assert SearchVariant.TITLE_YEAR == "title_year"
    assert SearchVariant.ORIGINAL_TITLE == "original_title"
    assert SearchVariant.ORIGINAL_TITLE_YEAR == "original_title_year"


def test_process_results_suppresses_busy_dialog_when_requested():
    from lib import search

    close_busy_dialog = MagicMock()
    silent_dialog = MagicMock()
    check_debrid_cached = MagicMock(return_value=[])
    with patch.object(search, "get_setting", return_value=False), patch.object(
        search, "close_busy_dialog", close_busy_dialog
    ), patch.object(search, "SilentProgressDialog", return_value=silent_dialog), patch.object(
        search, "check_debrid_cached", check_debrid_cached
    ):
        assert (
            search.process_results(
                [MagicMock()],
                "Show",
                "tv",
                "tv",
                True,
                2,
                suppress_dialog=True,
                suppress_busy_dialog=True,
            )
            == []
        )

    close_busy_dialog.assert_not_called()
    assert check_debrid_cached.call_args.args[4] is silent_dialog


def test_process_results_closes_busy_dialog_by_default():
    from lib import search

    close_busy_dialog = MagicMock()
    with patch.object(search, "get_setting", return_value=False), patch.object(
        search, "close_busy_dialog", close_busy_dialog
    ), patch.object(search, "SilentProgressDialog"), patch.object(
        search, "check_debrid_cached", return_value=[]
    ):
        search.process_results([MagicMock()], "Show", "tv", "tv", True, 2, suppress_dialog=True)

    close_busy_dialog.assert_called_once_with()


def test_super_quick_play_preserves_simkl_resume_metadata():
    params = {
        "ids": json.dumps({"tmdb_id": 123}),
        "simkl_session_id": "9",
        "simkl_resume_progress": "50",
    }
    playback_info = {"url": "https://stream.example/video"}
    player = MagicMock()

    with patch(
        "lib.search.get_setting",
        side_effect=lambda key, default=None: key in {"super_quick_play", "silent_resume"},
    ), patch("lib.search.cache.get", return_value=MagicMock()), patch(
        "lib.search._resolve_cached_source", return_value=playback_info
    ), patch("lib.search.JacktookPLayer", return_value=player):
        assert _handle_super_quick_play(params) is True

    assert playback_info["simkl_session_id"] == "9"
    assert playback_info["simkl_resume_progress"] == "50"
    player.run.assert_called_once_with(data=playback_info)


def test_super_quick_play_preserves_trakt_resume_metadata():
    params = {
        "ids": json.dumps({"tmdb_id": 123}),
        "trakt_playback_id": "9",
        "trakt_resume_progress": "50",
    }
    playback_info = {"url": "https://stream.example/video"}
    player = MagicMock()

    with patch(
        "lib.search.get_setting",
        side_effect=lambda key, default=None: key in {"super_quick_play", "silent_resume"},
    ), patch("lib.search.cache.get", return_value=MagicMock()), patch(
        "lib.search._resolve_cached_source", return_value=playback_info
    ), patch("lib.search.JacktookPLayer", return_value=player):
        assert _handle_super_quick_play(params) is True

    assert playback_info["trakt_playback_id"] == "9"
    assert playback_info["trakt_resume_progress"] == "50"
    player.run.assert_called_once_with(data=playback_info)


def test_run_search_entry_forwards_trakt_resume_to_source_selection():
    params = {
        "query": "Movie",
        "mode": "movies",
        "media_type": "movie",
        "ids": json.dumps({"tmdb_id": "123"}),
        "tv_data": "{}",
        "trakt_playback_id": "9",
        "trakt_resume_progress": "50",
    }

    with patch("lib.search._handle_super_quick_play", return_value=False), patch(
        "lib.search.search_client", return_value=[object()]
    ), patch("lib.search._process_search_results", return_value=[object()]), patch(
        "lib.search.set_content_type"
    ), patch("lib.search.set_watched_title"), patch(
        "lib.search.auto_play_enabled", return_value=False
    ), patch("lib.search.show_source_select", return_value=True) as show_source_select:
        run_search_entry(params)

    assert show_source_select.call_args.kwargs["playback_context"] == {
        "trakt_playback_id": "9",
        "trakt_resume_progress": "50",
    }


def test_run_search_entry_forwards_trakt_resume_to_autoplay():
    params = {
        "query": "Movie",
        "mode": "movies",
        "media_type": "movie",
        "ids": json.dumps({"tmdb_id": "123"}),
        "tv_data": "{}",
        "trakt_playback_id": "9",
        "trakt_resume_progress": "50",
    }

    with patch("lib.search._handle_super_quick_play", return_value=False), patch(
        "lib.search.search_client", return_value=[object()]
    ), patch("lib.search._process_search_results", return_value=[object()]), patch(
        "lib.search.set_content_type"
    ), patch("lib.search.set_watched_title"), patch(
        "lib.search.auto_play_enabled", return_value=True
    ), patch("lib.search.auto_play", return_value=True) as auto_play:
        run_search_entry(params)

    assert auto_play.call_args.kwargs["playback_context"] == {
        "trakt_playback_id": "9",
        "trakt_resume_progress": "50",
    }


def test_simple_search_submits_selected_stremio_addon_with_strict_whitelist():
    selected_addon = MagicMock()
    selected_addon.key.return_value = "selected|https://selected.example"
    selected_addon.url.return_value = "https://selected.example"
    executor = MagicMock()
    tasks = []

    with patch(
        "lib.search._get_source_manager_selection",
        return_value={"Stremio:selected|https://selected.example"},
    ), patch(
        "lib.search.get_setting", side_effect=lambda key, default=None: key == "stremio_enabled"
    ), patch("lib.search.get_selected_stream_addons", return_value=[selected_addon]):
        _submit_search_tasks(
            executor,
            tasks,
            MagicMock(),
            "Movie",
            "movies",
            "movie",
            0,
            0,
            {"imdb_id": "tt1234567"},
            "",
            None,
            "tt1234567",
            True,
        )

    assert len(tasks) == 1
    assert executor.submit.call_args.kwargs["scoped_addon_url"] == "https://selected.example"


def test_simple_search_excludes_unselected_stremio_addon_with_strict_whitelist():
    selected_addon = MagicMock()
    selected_addon.key.return_value = "selected|https://selected.example"
    selected_addon.url.return_value = "https://selected.example"
    unselected_addon = MagicMock()
    unselected_addon.key.return_value = "unselected|https://unselected.example"
    unselected_addon.url.return_value = "https://unselected.example"
    executor = MagicMock()
    tasks = []

    with patch(
        "lib.search._get_source_manager_selection",
        return_value={"Stremio:selected|https://selected.example"},
    ), patch(
        "lib.search.get_setting", side_effect=lambda key, default=None: key == "stremio_enabled"
    ), patch(
        "lib.search.get_selected_stream_addons", return_value=[selected_addon, unselected_addon]
    ):
        _submit_search_tasks(
            executor,
            tasks,
            MagicMock(),
            "Movie",
            "movies",
            "movie",
            0,
            0,
            {"imdb_id": "tt1234567"},
            "",
            None,
            "tt1234567",
            True,
        )

    assert len(tasks) == 1
    assert executor.submit.call_args.kwargs["scoped_addon_url"] == "https://selected.example"


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


@pytest.mark.parametrize("mode", ["movies", "tv"])
def test_show_source_select_passes_localized_tmdb_overview(mode):
    metadata = {"overview": "Localized TMDB synopsis"}
    ids = {"tmdb_id": "123"}

    with patch("lib.search.build_media_metadata", return_value=metadata) as build_metadata, patch(
        "lib.search.source_select", return_value=True
    ) as source_select_mock:
        show_source_select([object()], mode, ids, {}, "Title", mode, False)

    build_metadata.assert_called_once_with(ids, mode)
    assert source_select_mock.call_args.args[0]["overview"] == metadata["overview"]


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


def _auto_play_source(source_type):
    return SimpleNamespace(
        title="Selected source",
        quality="1080p",
        type=source_type,
        indexer=Indexer.JACKETT,
        debridType="",
        infoHash="abc123",
        url="https://example.com/file.torrent",
        stremioMetadata=None,
    )


def _autoplay_setting(key, default=None):
    return {
        "auto_play_quality": "1080p",
        "torrent_enable": True,
        "torrent_client": Players.JACKTORR,
    }.get(key, default)


def test_auto_play_hydrates_localized_overview_for_jacktorr():
    from lib import search

    source = _auto_play_source(IndexerType.TORRENT)
    synopsis = "Localized TMDB synopsis"
    with patch("lib.search._prepare_stremio_results", return_value=[source]), patch(
        "lib.search.clean_auto_play_undesired", return_value=[source]
    ), patch("lib.search.get_setting", side_effect=_autoplay_setting), patch(
        "lib.search.build_media_metadata", return_value={"overview": synopsis}
    ) as build_metadata, patch(
        "lib.search.resolve_playback_url", side_effect=lambda data: data
    ) as resolve_playback_url, patch("lib.search.JacktookPLayer"):
        assert search.auto_play([source], {"tmdb_id": "123"}, {}, "movies") is True

    build_metadata.assert_called_once_with({"tmdb_id": "123"}, "movies")
    assert resolve_playback_url.call_args.kwargs["data"]["description"] == synopsis


def test_auto_play_preserves_description_through_stremio_resolution():
    from lib import search

    source = _auto_play_source(IndexerType.TORRENT)
    source.stremioMetadata = {"infoHash": "a" * 40}
    synopsis = "Localized TMDB synopsis"
    with patch("lib.search._prepare_stremio_results", return_value=[source]), patch(
        "lib.search.clean_auto_play_undesired", return_value=[source]
    ), patch("lib.search.get_setting", side_effect=_autoplay_setting), patch(
        "lib.search._autoplay_description", return_value=synopsis
    ), patch(
        "lib.search._resolve_stremio_source", return_value={"url": "plugin://resolved"}
    ) as resolve_stremio_source, patch("lib.search.JacktookPLayer"):
        assert search.auto_play([source], {"tmdb_id": "123"}, {}, "movies") is True

    assert resolve_stremio_source.call_args.args[1]["description"] == synopsis


def test_auto_play_skips_metadata_hydration_for_direct_sources():
    from lib import search

    source = _auto_play_source(IndexerType.DIRECT)
    with patch("lib.search._prepare_stremio_results", return_value=[source]), patch(
        "lib.search.clean_auto_play_undesired", return_value=[source]
    ), patch("lib.search.get_setting", side_effect=_autoplay_setting), patch(
        "lib.search.build_media_metadata"
    ) as build_metadata, patch(
        "lib.search.resolve_playback_url", side_effect=lambda data: data
    ), patch("lib.search.JacktookPLayer"):
        assert search.auto_play([source], {"tmdb_id": "123"}, {}, "movies") is True

    build_metadata.assert_not_called()


def test_run_search_entry_does_not_repeat_stremio_rejection_after_autoplay_fallback():
    from lib import search

    source = TorrentStream(
        title="Unsupported source",
        addonKey="org.example.addon|https://example.com",
        stremioMetadata={"externalUrl": "https://external.example/watch"},
    )
    notifications = []
    params = {
        "query": "Movie",
        "mode": "movies",
        "media_type": "movies",
        "ids": json.dumps({"imdb_id": "tt123"}),
    }

    with patch("lib.search._handle_super_quick_play", return_value=False), patch(
        "lib.search.search_client", return_value=[source]
    ), patch("lib.search._process_search_results", return_value=[source]), patch(
        "lib.search.set_content_type"
    ), patch("lib.search.set_watched_title"), patch(
        "lib.search.auto_play_enabled", return_value=True
    ), patch("lib.search.notification", side_effect=notifications.append), patch(
        "lib.search.show_source_select", wraps=search.show_source_select
    ) as show_source_select_mock, patch("lib.search.source_select") as source_select_mock, patch(
        "lib.search.cancel_playback"
    ) as cancel_playback_mock:
        run_search_entry(params)

    assert notifications == [
        "External web pages are not playable sources.",
        "No suitable source found for auto play.",
    ]
    assert show_source_select_mock.call_args.kwargs["rejection_already_notified"] is True
    source_select_mock.assert_not_called()
    cancel_playback_mock.assert_called_once_with()


def test_run_search_entry_falls_back_to_source_selection_after_quality_failure():
    source = _auto_play_source(IndexerType.TORRENT)
    params = {
        "query": "Movie",
        "mode": "movies",
        "media_type": "movies",
        "ids": json.dumps({"imdb_id": "tt123"}),
    }

    with patch("lib.search._handle_super_quick_play", return_value=False), patch(
        "lib.search.search_client", return_value=[source]
    ), patch("lib.search._process_search_results", return_value=[source]), patch(
        "lib.search.set_content_type"
    ), patch("lib.search.set_watched_title"), patch(
        "lib.search.auto_play_enabled", return_value=True
    ), patch("lib.search.get_setting", return_value="2160p"), patch(
        "lib.search.build_media_metadata", return_value={}
    ), patch("lib.search.notification") as notification_mock, patch(
        "lib.search.source_select", return_value=True
    ) as source_select_mock, patch("lib.search.cancel_playback") as cancel_playback_mock:
        run_search_entry(params)

    notification_mock.assert_called_once_with("No sources found with the preferred quality.")
    assert source_select_mock.call_args.kwargs["sources"] == [source]
    cancel_playback_mock.assert_not_called()


def test_run_search_entry_falls_back_to_source_selection_after_resolution_failure():
    source = TorrentStream(
        title="Resolvable source",
        quality="1080p",
        addonKey="org.example.addon|https://example.com",
        stremioMetadata={"url": "https://media.example/movie.mkv"},
    )
    params = {
        "query": "Movie",
        "mode": "movies",
        "media_type": "movies",
        "ids": json.dumps({"imdb_id": "tt123"}),
    }

    with patch("lib.search._handle_super_quick_play", return_value=False), patch(
        "lib.search.search_client", return_value=[source]
    ), patch("lib.search._process_search_results", return_value=[source]), patch(
        "lib.search.set_content_type"
    ), patch("lib.search.set_watched_title"), patch(
        "lib.search.auto_play_enabled", return_value=True
    ), patch("lib.search.get_setting", return_value="1080p"), patch(
        "lib.search._resolve_stremio_source",
        side_effect=StremioPlaybackError("resolution_failed", "Unable to resolve source."),
    ), patch("lib.search.build_media_metadata", return_value={}), patch(
        "lib.search.notification"
    ) as notification_mock, patch("lib.search.source_select", return_value=True) as source_select_mock, patch(
        "lib.search.cancel_playback"
    ) as cancel_playback_mock:
        run_search_entry(params)

    notification_mock.assert_called_once_with("Unable to resolve source.")
    assert source_select_mock.call_args.kwargs["sources"] == [source]
    cancel_playback_mock.assert_not_called()


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
    ), patch("lib.search._process_search_results", return_value=[object()]), patch(
        "lib.search.set_content_type"
    ), patch("lib.search.set_watched_title"), patch(
        "lib.search.auto_play_enabled", return_value=False
    ), patch("lib.search.show_source_select", return_value=False), patch(
        "lib.search.cancel_playback"
    ) as cancel_mock:
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
    ), patch("lib.search._process_search_results", return_value=[object()]), patch(
        "lib.search.set_content_type"
    ), patch("lib.search.set_watched_title"), patch(
        "lib.search.auto_play_enabled", return_value=False
    ), patch("lib.search.show_source_select", return_value=False), patch(
        "lib.search.cancel_playback"
    ) as cancel_mock:
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


def test_run_search_entry_caches_nonempty_cancelled_episode_results():
    params = {
        "query": "Show",
        "mode": "tv",
        "media_type": "tv",
        "ids": json.dumps({"tmdb_id": "123"}),
        "tv_data": json.dumps({"season": 2, "episode": 1}),
    }
    partial_results = [object()]

    with patch("lib.search._handle_super_quick_play", return_value=False), patch(
        "lib.search.search_client", side_effect=SearchCancelled(partial_results)
    ), patch("lib.search._build_search_cache_scope", return_value="scope"), patch(
        "lib.search.cache_results"
    ) as cache_results_mock, patch(
        "lib.search._process_search_results", return_value=partial_results
    ), patch("lib.search.set_content_type"), patch("lib.search.set_watched_title"), patch(
        "lib.search.auto_play_enabled", return_value=False
    ), patch("lib.search.show_source_select", return_value=True):
        run_search_entry(params)

    cache_results_mock.assert_called_once_with(
        partial_results,
        "Show",
        "tv",
        "tv",
        1,
        2,
        cache_scope="scope",
    )


def test_run_search_entry_does_not_cache_empty_cancelled_episode_results():
    params = {
        "query": "Show",
        "mode": "tv",
        "media_type": "tv",
        "ids": json.dumps({"tmdb_id": "123"}),
        "tv_data": json.dumps({"season": 2, "episode": 1}),
    }

    with patch("lib.search._handle_super_quick_play", return_value=False), patch(
        "lib.search.search_client", side_effect=SearchCancelled([])
    ), patch("lib.search.cache_results") as cache_results_mock, patch(
        "lib.search.set_content_type"
    ), patch("lib.search.set_watched_title"), patch("lib.search.notification"), patch(
        "lib.search.cancel_playback"
    ):
        run_search_entry(params)

    cache_results_mock.assert_not_called()


def test_is_source_enabled_returns_true_when_cache_empty():
    with patch("lib.search.cache") as mock_cache:
        mock_cache.get.return_value = None
        assert _is_source_enabled(Indexer.JACKETT) is True
        assert _is_source_enabled(Indexer.STREMIO, "some_addon") is True


def test_search_reconciles_new_settings_source_before_cache_and_eligibility():
    """New Settings sources join the whitelist without re-enabling known deselections."""
    cached = [MagicMock()]
    stored = {
        "source_manager_selection": json.dumps(["Jackett"]),
        "source_manager_known_keys": json.dumps(["Jackett", "Prowlarr"]),
    }

    def cache_get_side_effect(key):
        return stored.get(key)

    def cache_set_side_effect(key, value, **kwargs):
        stored[key] = value

    def setting_side_effect(key, default=None):
        return key == "jacktookburst_enabled"

    with (
        patch("lib.search.cache") as mock_cache,
        patch("lib.search.get_setting", side_effect=setting_side_effect),
        patch("lib.search.get_selected_stream_addons", return_value=[]),
        patch("lib.search.close_busy_dialog"),
        patch("lib.search._infer_tmdb_year", return_value=2020),
        patch("lib.search._build_title_fallback_queries", return_value=["Movie"]),
        patch("lib.search._check_search_caches", return_value=cached),
    ):
        mock_cache.get.side_effect = cache_get_side_effect
        mock_cache.set.side_effect = cache_set_side_effect
        assert search_client("Movie", {}, "movies", "movie", False, 0, 0) == cached
        assert _is_source_enabled(Indexer.BURST) is True
        assert _is_source_enabled(Indexer.PROWLARR) is False

    saved = {call.args[0]: json.loads(call.args[1]) for call in mock_cache.set.call_args_list}
    assert saved["source_manager_selection"] == ["Jackett", "Burst"]
    assert saved["source_manager_known_keys"] == ["Jackett", "Prowlarr", "Burst"]


def test_search_preserves_explicit_empty_source_selection():
    """An explicit empty whitelist excludes enabled providers after reconciliation."""
    cached = [MagicMock()]
    stored = {
        "source_manager_selection": "[]",
        "source_manager_known_keys": json.dumps(["Jackett", "Prowlarr"]),
    }

    with (
        patch("lib.search.cache") as mock_cache,
        patch(
            "lib.search.get_setting",
            side_effect=lambda key, default=None: key in ("jackett_enabled", "prowlarr_enabled"),
        ),
        patch("lib.search.get_selected_stream_addons", return_value=[]),
        patch("lib.search.close_busy_dialog"),
        patch("lib.search._infer_tmdb_year", return_value=2020),
        patch("lib.search._build_title_fallback_queries", return_value=["Movie"]),
        patch("lib.search._check_search_caches", return_value=cached),
    ):
        mock_cache.get.side_effect = stored.get
        assert search_client("Movie", {}, "movies", "movie", False, 0, 0) == cached
        assert json.loads(stored["source_manager_selection"]) == []
        assert _is_source_enabled(Indexer.JACKETT) is False
        assert _is_source_enabled(Indexer.PROWLARR) is False
        mock_cache.set.assert_not_called()


def test_search_initializes_missing_source_selection():
    """A missing selection cache initializes the enabled sources."""
    cached = [MagicMock()]
    stored = {}

    def cache_set_side_effect(key, value, **kwargs):
        stored[key] = value

    with (
        patch("lib.search.cache") as mock_cache,
        patch(
            "lib.search.get_setting", side_effect=lambda key, default=None: key == "jackett_enabled"
        ),
        patch("lib.search.get_selected_stream_addons", return_value=[]),
        patch("lib.search.close_busy_dialog"),
        patch("lib.search._infer_tmdb_year", return_value=2020),
        patch("lib.search._build_title_fallback_queries", return_value=["Movie"]),
        patch("lib.search._check_search_caches", return_value=cached),
    ):
        mock_cache.get.side_effect = stored.get
        mock_cache.set.side_effect = cache_set_side_effect
        assert search_client("Movie", {}, "movies", "movie", False, 0, 0) == cached

    assert json.loads(stored["source_manager_selection"]) == ["Jackett"]
    assert json.loads(stored["source_manager_known_keys"]) == ["Jackett"]


def test_search_cache_scope_changes_for_enabled_search_providers():
    settings = {
        "jackett_enabled": False,
        "prowlarr_enabled": False,
        "jacktookburst_enabled": False,
        "jackgram_enabled": False,
        "external_scraper_enabled": False,
        "stremio_enabled": False,
        "torrent_enable": False,
        "real_debrid_enabled": False,
        "alldebrid_enabled": False,
        "torbox_enabled": False,
        "offcloud_enabled": False,
        "premiumize_enabled": False,
        "debrider_enabled": False,
        "easydebrid_enabled": False,
        "external_scraper_module": "",
    }

    with patch(
        "lib.search.get_setting", side_effect=lambda key, default=None: settings.get(key, default)
    ), patch(
        "lib.search.cache.get", side_effect=lambda key: {"source_manager_selection": "[]"}.get(key)
    ):
        base_scope = _build_search_cache_scope()
        for key in (
            "jackett_enabled",
            "prowlarr_enabled",
            "jacktookburst_enabled",
            "jackgram_enabled",
            "external_scraper_enabled",
            "stremio_enabled",
        ):
            settings[key] = True
            assert _build_search_cache_scope() != base_scope
            settings[key] = False


def test_is_source_enabled_returns_true_when_cache_invalid():
    with patch("lib.search.cache") as mock_cache:
        mock_cache.get.return_value = "not-json"
        assert _is_source_enabled(Indexer.JACKETT) is True


def test_is_source_enabled_returns_false_when_cache_is_explicitly_empty():
    with patch("lib.search.cache") as mock_cache:
        mock_cache.get.return_value = "[]"
        assert _is_source_enabled(Indexer.JACKETT) is False
        assert _is_source_enabled(Indexer.STREMIO, "some_addon") is False


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
def test_is_source_enabled_strict_whitelist_ignores_settings(mock_get_setting):
    """A source enabled in settings but deselected in Manage Sources must not search."""

    def setting_side_effect(key):
        return key in ("jackett_enabled", "prowlarr_enabled")

    mock_get_setting.side_effect = setting_side_effect
    with patch("lib.search.cache") as mock_cache:
        mock_cache.get.return_value = json.dumps(["Jackett"])
        assert _is_source_enabled(Indexer.JACKETT) is True
        # Prowlarr is enabled in settings but was deselected in Manage Sources
        assert _is_source_enabled(Indexer.PROWLARR) is False
        # Burst is not enabled in settings and not selected
        assert _is_source_enabled(Indexer.BURST) is False


@patch("lib.search.get_setting")
def test_is_source_enabled_external_scraper_respects_selection(mock_get_setting):
    """External scraper must respect Manage Sources selection by module name."""

    def setting_side_effect(key):
        if key == "external_scraper_enabled":
            return True
        if key == "external_scraper_module_name":
            return "cocoscrapers"
        return False

    mock_get_setting.side_effect = setting_side_effect
    with patch("lib.search.cache") as mock_cache:
        mock_cache.get.return_value = json.dumps(["Jackett"])
        assert _is_source_enabled(Indexer.EXTERNAL_SCRAPER) is False

    with patch("lib.search.cache") as mock_cache:
        mock_cache.get.return_value = json.dumps(["cocoscrapers"])
        assert _is_source_enabled(Indexer.EXTERNAL_SCRAPER) is True

    # Fallback literal supports older caches
    with patch("lib.search.cache") as mock_cache:
        mock_cache.get.return_value = json.dumps(["External Scraper"])
        assert _is_source_enabled(Indexer.EXTERNAL_SCRAPER) is True


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
@patch("lib.search.get_addon_display_name")
def test_submit_search_tasks_managed_filters_stremio_addons(
    mock_get_display_name,
    mock_get_addons,
    mock_cache,
    mock_get_setting,
):
    mock_get_setting.return_value = True
    mock_cache.get.return_value = json.dumps(["Stremio:addon1|url1"])
    mock_get_display_name.side_effect = lambda addon: addon.manifest.name

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
            patch(
                "lib.utils.player.utils.get_autoscrape_results_cache_key", return_value="as:123_1_2"
            ),
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
            patch(
                "lib.utils.player.utils.get_autoscrape_results_cache_key",
                return_value="as:tt999_2_3",
            ),
            patch("lib.search.cache_results") as mock_cache_results,
        ):
            result = _check_search_caches("q", ids, "tv", "tv", 3, 2, "scope")

        assert result == autoscrape_results
        mock_cache_results.assert_called_once_with(
            autoscrape_results,
            "q",
            "tv",
            "tv",
            3,
            2,
            cache_scope="scope",
        )


# ---------------------------------------------------------------------------
# search_client  (orchestration)
# ---------------------------------------------------------------------------


class TestSearchClient:
    """Cover orchestration logic of search_client (branching, cache, search dispatch)."""

    def test_rescrape_skips_cache_reads_but_writes_results(self):
        """rescrape=True bypasses cache reads but replaces cached search results."""
        with (
            patch("lib.search.close_busy_dialog"),
            patch("lib.search._infer_tmdb_year", return_value=2020),
            patch("lib.search._build_title_fallback_queries", return_value=["q 2020"]),
            patch("lib.search.reconcile_source_selection"),
            patch("lib.search._build_search_cache_scope", return_value="scope"),
            patch("lib.search._check_search_caches") as mock_check,
            patch("lib.search.get_setting", return_value="0"),
            patch("lib.search._run_simple_search", return_value=[]),
            patch("lib.search.cache_results") as mock_cache_results,
        ):
            search_client("q", {}, "movies", "movie", rescrape=True, season=0, episode=0)

        mock_check.assert_not_called()
        mock_cache_results.assert_called_once_with(
            [], "q", "movies", "movie", 0, 0, cache_scope="scope"
        )

    def test_not_rescrape_cache_hit_returns_early(self):
        """Not rescrape + cache hit → return cached, no search."""
        cached = [MagicMock()]
        with (
            patch("lib.search.close_busy_dialog"),
            patch("lib.search._infer_tmdb_year", return_value=2020),
            patch("lib.search._build_title_fallback_queries", return_value=["q 2020"]),
            patch("lib.search.reconcile_source_selection"),
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

    @pytest.mark.parametrize(
        ("jackgram_only", "expected_scope", "expected_addon_url"),
        [
            (True, "scope:jackgram", ""),
            (False, "scope", "https://addon.example"),
        ],
    )
    def test_jackgram_only_uses_an_isolated_cache_scope(
        self, jackgram_only, expected_scope, expected_addon_url
    ):
        results = [MagicMock()]
        with patch("lib.search.close_busy_dialog"), patch(
            "lib.search._infer_tmdb_year", return_value=2020
        ), patch("lib.search._build_title_fallback_queries", return_value=["q"]), patch(
            "lib.search.reconcile_source_selection"
        ), patch(
            "lib.search._build_search_cache_scope", return_value="scope"
        ) as build_scope, patch(
            "lib.search._check_search_caches", return_value=None
        ) as check_cache, patch("lib.search.get_setting", return_value="0"), patch(
            "lib.search._run_simple_search", return_value=results
        ), patch("lib.search.cache_results") as cache_results_mock:
            result = search_client(
                "q",
                {},
                "movies",
                "movie",
                rescrape=False,
                season=0,
                episode=0,
                scoped_addon_url="https://addon.example",
                jackgram_only=jackgram_only,
            )

        assert result == results
        build_scope.assert_called_once_with(expected_addon_url)
        check_cache.assert_called_once_with(
            "q",
            {},
            "movies",
            "movie",
            0,
            0,
            expected_scope,
            allow_autoscrape_fallback=not jackgram_only,
        )
        cache_results_mock.assert_called_once_with(
            results, "q", "movies", "movie", 0, 0, cache_scope=expected_scope
        )

    def test_jackgram_only_filters_legacy_isolated_cache_results(self):
        matching = MagicMock(title="Love Story 1080p")
        non_matching = MagicMock(title="The Witcher S03E01")
        cached = [matching, non_matching]
        with patch("lib.search.close_busy_dialog"), patch(
            "lib.search._infer_tmdb_year", return_value=2020
        ), patch("lib.search._build_title_fallback_queries", return_value=["love story"]), patch(
            "lib.search.reconcile_source_selection"
        ), patch("lib.search._build_search_cache_scope", return_value="scope"), patch(
            "lib.search._check_search_caches", return_value=cached
        ) as check_cache, patch("lib.search._run_simple_search") as mock_simple:
            result = search_client(
                "LOVE  story",
                {},
                "movies",
                "movie",
                rescrape=False,
                season=0,
                episode=0,
                jackgram_only=True,
            )

        assert result == [matching]
        check_cache.assert_called_once_with(
            "LOVE  story",
            {},
            "movies",
            "movie",
            0,
            0,
            "scope:jackgram",
            allow_autoscrape_fallback=False,
        )
        mock_simple.assert_not_called()

    def test_jackgram_only_tv_search_skips_autoscrape_cache(self):
        fresh_results = [MagicMock()]
        with patch("lib.search.close_busy_dialog"), patch(
            "lib.search.reconcile_source_selection"
        ), patch("lib.search._infer_tmdb_year", return_value=2020), patch(
            "lib.search._build_title_fallback_queries", return_value=["Show"]
        ), patch("lib.search._build_search_cache_scope", return_value="scope"), patch(
            "lib.search.get_cached_results", return_value=None
        ), patch(
            "lib.utils.player.utils.get_autoscrape_results_cache_key"
        ) as autoscrape_key, patch("lib.search.get_setting", return_value="0"), patch(
            "lib.search._run_simple_search", return_value=fresh_results
        ) as mock_simple, patch("lib.search.cache_results"):
            result = search_client(
                "Show",
                {"tmdb_id": "123"},
                "tv",
                "tv",
                rescrape=False,
                season=1,
                episode=2,
                jackgram_only=True,
            )

        assert result == fresh_results
        autoscrape_key.assert_not_called()
        mock_simple.assert_called_once()

    def test_cache_miss_detailed_dialog_branch(self):
        """Cache miss + search_dialog_style=1 → calls _run_detailed_search."""
        expected = [MagicMock()]
        with (
            patch("lib.search.close_busy_dialog"),
            patch("lib.search._infer_tmdb_year", return_value=2020),
            patch("lib.search._build_title_fallback_queries", return_value=["q 2020"]),
            patch("lib.search.reconcile_source_selection"),
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
            patch("lib.search.reconcile_source_selection"),
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
            patch("lib.search.reconcile_source_selection"),
            patch("lib.search._build_search_cache_scope", return_value="scope"),
            patch("lib.search._check_search_caches", return_value=None),
            patch(
                "lib.search.get_setting", return_value="1"
            ),  # would trigger detailed, but show_dialog=False
            patch("lib.search._run_detailed_search") as mock_detailed,
            patch("lib.search._run_simple_search", return_value=expected) as mock_simple,
            patch("lib.search.cache_results"),
        ):
            result = search_client(
                "q",
                {},
                "movies",
                "movie",
                rescrape=False,
                season=0,
                episode=0,
                show_dialog=False,
            )

        assert result == expected
        mock_simple.assert_called_once()
        mock_detailed.assert_not_called()

    def test_detailed_search_failure_falls_back_to_simple_search(self):
        """Detailed XML UI failure → search continues through simple progress."""
        expected = [MagicMock()]
        with (
            patch("lib.search.close_busy_dialog"),
            patch("lib.search._infer_tmdb_year", return_value=2020),
            patch("lib.search._build_title_fallback_queries", return_value=["q 2020"]),
            patch("lib.search.reconcile_source_selection"),
            patch("lib.search._build_search_cache_scope", return_value="scope"),
            patch("lib.search._check_search_caches", return_value=None),
            patch("lib.search.get_setting", return_value="1"),
            patch(
                "lib.search._run_detailed_search", side_effect=RuntimeError("xml failed")
            ) as mock_detailed,
            patch("lib.search._run_simple_search", return_value=expected) as mock_simple,
            patch("lib.search.cache_results") as mock_cache,
        ):
            result = search_client("q", {}, "movies", "movie", rescrape=False, season=0, episode=0)

        assert result == expected
        mock_detailed.assert_called_once()
        mock_simple.assert_called_once()
        assert mock_simple.call_args[0][9] is True
        mock_cache.assert_called_once_with(
            expected, "q", "movies", "movie", 0, 0, cache_scope="scope"
        )

    def test_passes_year_to_infer_when_none(self):
        """year=None → _infer_tmdb_year is called."""
        with (
            patch("lib.search.close_busy_dialog"),
            patch("lib.search._infer_tmdb_year", return_value=2020) as mock_infer,
            patch("lib.search._build_title_fallback_queries", return_value=["q"]),
            patch("lib.search.reconcile_source_selection"),
            patch("lib.search._build_search_cache_scope", return_value="scope"),
            patch("lib.search._check_search_caches", return_value=None),
            patch("lib.search.get_setting", return_value="0"),
            patch("lib.search._run_simple_search", return_value=[]),
            patch("lib.search.cache_results"),
        ):
            search_client(
                "q", {"tmdb_id": "123"}, "movies", "movie", rescrape=False, season=0, episode=0
            )

        mock_infer.assert_called_once_with({"tmdb_id": "123"}, "movies")

    def test_does_not_infer_year_when_provided(self):
        """year=2010 → _infer_tmdb_year is NOT called."""
        with (
            patch("lib.search.close_busy_dialog"),
            patch("lib.search._infer_tmdb_year") as mock_infer,
            patch("lib.search._build_title_fallback_queries", return_value=["q"]),
            patch("lib.search.reconcile_source_selection"),
            patch("lib.search._build_search_cache_scope", return_value="scope"),
            patch("lib.search._check_search_caches", return_value=None),
            patch("lib.search.get_setting", return_value="0"),
            patch("lib.search._run_simple_search", return_value=[]),
            patch("lib.search.cache_results"),
        ):
            search_client(
                "q", {}, "movies", "movie", rescrape=False, season=0, episode=0, year=2010
            )

        mock_infer.assert_not_called()
