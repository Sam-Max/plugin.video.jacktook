from copy import deepcopy
from unittest.mock import MagicMock, patch

from lib.api.trakt.trakt_cache import default_activities
from lib.services.trakt_sync import TraktSyncService


def test_get_changed_buckets_detects_expected_activity_groups():
    service = TraktSyncService(api=MagicMock(), monitor=MagicMock())
    previous = default_activities()
    latest = deepcopy(previous)
    latest["movies"]["watched_at"] = "2026-03-13T18:00:00.000Z"
    latest["episodes"]["paused_at"] = "2026-03-13T18:01:00.000Z"
    latest["lists"]["updated_at"] = "2026-03-13T18:02:00.000Z"

    changes = service._get_changed_buckets(previous, latest)

    assert "watched_movies" in changes
    assert "progress_episodes" in changes
    assert "lists" in changes


def test_sync_activities_applies_changed_buckets():
    api = MagicMock()
    api.sync.get_last_activities.return_value = {"movies": {"watched_at": "new"}}
    service = TraktSyncService(api=api, monitor=MagicMock())

    with patch("lib.services.trakt_sync.reset_activity", return_value={"movies": {"watched_at": "old"}}), patch.object(
        service, "_get_changed_buckets", return_value={"watched_movies", "lists"}
    ) as changed_buckets, patch.object(service, "_apply_activity_changes") as apply_changes:
        result = service.sync_activities()

    changed_buckets.assert_called_once()
    apply_changes.assert_called_once_with({"watched_movies", "lists"})
    assert result == {"watched_movies", "lists"}


def test_sync_activities_logs_changed_buckets():
    api = MagicMock()
    api.sync.get_last_activities.return_value = {"movies": {"watched_at": "new"}}
    service = TraktSyncService(api=api, monitor=MagicMock())

    with patch("lib.services.trakt_sync.reset_activity", return_value={"movies": {"watched_at": "old"}}), patch.object(
        service, "_get_changed_buckets", return_value={"watched_movies", "lists"}
    ), patch.object(service, "_apply_activity_changes"), patch(
        "lib.services.trakt_sync.kodilog"
    ) as kodilog:
        service.sync_activities()

    assert any(
        "changed buckets = lists, watched_movies" in str(call.args[0])
        for call in kodilog.call_args_list
    )


def test_invalidate_cached_buckets_targets_expected_caches():
    service = TraktSyncService(api=MagicMock(), monitor=MagicMock())

    with patch("lib.services.trakt_sync.lists_cache.delete_prefix") as delete_prefix, patch(
        "lib.services.trakt_sync.clear_trakt_favorites"
    ) as clear_favorites, patch(
        "lib.services.trakt_sync.clear_trakt_list_data"
    ) as clear_list_data, patch(
        "lib.services.trakt_sync.clear_trakt_list_contents_data"
    ) as clear_list_contents:
        service.invalidate_cached_buckets(
            {"collection_movies", "favorites_movies", "recommendations_shows", "lists"}
        )

    delete_prefix.assert_any_call("trakt_movies_collection_")
    delete_prefix.assert_any_call("trakt_recommendations_shows")
    clear_favorites.assert_called_once_with()
    clear_list_data.assert_any_call("my_lists")
    clear_list_data.assert_any_call("liked_lists")
    clear_list_contents.assert_any_call("my_lists")
    clear_list_contents.assert_any_call("liked_lists")


def test_sync_watched_movies_replaces_cache_data():
    api = MagicMock()
    api.movies.get_watched_movies.return_value = [
        {
            "movie": {"ids": {"tmdb": 10}, "title": "Movie"},
            "last_watched_at": "2026-03-13T18:03:00.000Z",
        }
    ]
    service = TraktSyncService(api=api, monitor=MagicMock())

    with patch("lib.services.trakt_sync.trakt_watched_cache.set_bulk_movie_watched") as set_bulk:
        service.sync_watched_movies()

    set_bulk.assert_called_once_with(
        [("movie", "10", None, None, "2026-03-13T18:03:00.000Z", "Movie")]
    )
