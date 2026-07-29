from copy import deepcopy
from unittest.mock import MagicMock, patch

import pytest

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


def test_sync_activities_advances_checkpoint_after_applying_changed_buckets():
    api = MagicMock()
    latest = {"movies": {"watched_at": "new"}}
    previous = {"movies": {"watched_at": "old"}}
    api.sync.get_last_activities.return_value = latest
    service = TraktSyncService(api=api, monitor=MagicMock())
    events = []

    with patch(
        "lib.services.trakt_sync.get_activity",
        return_value=previous,
    ), patch.object(
        service, "_get_changed_buckets", return_value={"watched_movies", "lists"}
    ) as changed_buckets, patch.object(
        service, "_apply_activity_changes", side_effect=lambda _changes: events.append("apply")
    ) as apply_changes, patch(
        "lib.services.trakt_sync.set_activity",
        side_effect=lambda _activities: events.append("checkpoint"),
    ) as set_activity:
        result = service.sync_activities()

    changed_buckets.assert_called_once()
    apply_changes.assert_called_once_with({"watched_movies", "lists"})
    set_activity.assert_called_once_with(latest)
    assert events == ["apply", "checkpoint"]
    assert result == {"watched_movies", "lists"}


def test_sync_activities_preserves_checkpoint_when_bucket_application_fails():
    api = MagicMock()
    api.sync.get_last_activities.return_value = {"movies": {"watched_at": "new"}}
    service = TraktSyncService(api=api, monitor=MagicMock())

    with patch(
        "lib.services.trakt_sync.get_activity",
        return_value={"movies": {"watched_at": "old"}},
    ), patch.object(service, "_get_changed_buckets", return_value={"watched_movies"}), patch.object(
        service, "_apply_activity_changes", side_effect=RuntimeError("sync failed")
    ), patch("lib.services.trakt_sync.set_activity") as set_activity:
        with pytest.raises(RuntimeError, match="sync failed"):
            service.sync_activities()

    set_activity.assert_not_called()


def test_sync_activities_advances_checkpoint_when_no_buckets_changed():
    api = MagicMock()
    latest = {"movies": {"watched_at": "same"}}
    api.sync.get_last_activities.return_value = latest
    service = TraktSyncService(api=api, monitor=MagicMock())

    with patch("lib.services.trakt_sync.get_activity", return_value=latest), patch.object(
        service, "_get_changed_buckets", return_value=set()
    ), patch.object(service, "_apply_activity_changes") as apply_changes, patch(
        "lib.services.trakt_sync.set_activity"
    ) as set_activity:
        result = service.sync_activities()

    apply_changes.assert_not_called()
    set_activity.assert_called_once_with(latest)
    assert result == set()


def test_sync_activities_logs_changed_buckets():
    api = MagicMock()
    api.sync.get_last_activities.return_value = {"movies": {"watched_at": "new"}}
    service = TraktSyncService(api=api, monitor=MagicMock())

    with patch(
        "lib.services.trakt_sync.get_activity",
        return_value={"movies": {"watched_at": "old"}},
    ), patch.object(
        service, "_get_changed_buckets", return_value={"watched_movies", "lists"}
    ), patch.object(service, "_apply_activity_changes"), patch(
        "lib.services.trakt_sync.set_activity"
    ), patch("lib.services.trakt_sync.kodilog") as kodilog:
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


def test_run_retries_after_startup_failure_without_busy_loop():
    monitor = MagicMock()
    monitor.abortRequested.side_effect = [False, True]
    service = TraktSyncService(api=MagicMock(), monitor=monitor)
    startup_error = RuntimeError("startup failed")

    with patch.object(service, "_is_trakt_available", return_value=True), patch.object(
        service, "_wait_for_next_cycle", return_value=False
    ) as wait_for_next_cycle, patch.object(
        service, "_services_paused", return_value=False
    ), patch.object(
        service, "sync_activities", side_effect=[startup_error, set()]
    ) as sync_activities, patch.object(service, "_log_sync_failure") as log_failure:
        service.run()

    assert sync_activities.call_count == 2
    wait_for_next_cycle.assert_called_once_with()
    log_failure.assert_any_call("startup", True, startup_error)


def test_run_retries_after_periodic_failure_without_busy_loop():
    monitor = MagicMock()
    monitor.abortRequested.side_effect = [False, False, True]
    service = TraktSyncService(api=MagicMock(), monitor=monitor)
    periodic_error = RuntimeError("periodic failed")

    with patch.object(service, "_is_trakt_available", return_value=True), patch.object(
        service, "_wait_for_next_cycle", return_value=False
    ) as wait_for_next_cycle, patch.object(
        service, "_services_paused", return_value=False
    ), patch.object(
        service, "sync_activities", side_effect=[set(), periodic_error, set()]
    ) as sync_activities, patch.object(service, "_log_sync_failure") as log_failure:
        service.run()

    assert sync_activities.call_count == 3
    assert wait_for_next_cycle.call_count == 2
    log_failure.assert_any_call("periodic", False, periodic_error)
