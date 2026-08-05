import json
from unittest.mock import MagicMock, patch

from lib.services.simkl_sync import DOMAIN_BUCKETS, SimklSyncService


def activities(all_timestamp="2026-08-05T12:00:00Z", **changes):
    result = {"all": all_timestamp, "tv_shows": {}, "movies": {}, "anime": {}}
    for domain, bucket, timestamp in changes.get("values", []):
        result[domain][bucket] = timestamp
    return result


def test_sync_is_gated_when_simkl_is_not_authenticated():
    api = MagicMock()
    service = SimklSyncService(api=api, monitor=MagicMock())

    with patch("lib.services.simkl_sync.is_simkl_authenticated", return_value=False):
        service.run()

    api.get_activities.assert_not_called()


def test_first_successful_check_invalidates_all_namespaces_then_persists_baseline():
    latest = activities()
    api = MagicMock()
    api.get_activities.return_value = latest
    service = SimklSyncService(api=api, monitor=MagicMock())
    events = []

    with patch.object(service, "_get_activities", return_value=None), patch(
        "lib.services.simkl_sync.invalidate_library_cache",
        side_effect=lambda: events.append("library"),
    ), patch(
        "lib.services.simkl_sync.invalidate_playback_cache",
        side_effect=lambda: events.append("playback"),
    ), patch(
        "lib.services.simkl_sync.invalidate_watched_cache",
        side_effect=lambda: events.append("watched"),
    ), patch(
        "lib.services.simkl_sync.invalidate_ratings_cache",
        side_effect=lambda: events.append("ratings"),
    ), patch.object(service, "_set_activities", side_effect=lambda _: events.append("marker")):
        result = service.sync_activities()

    assert result == set(DOMAIN_BUCKETS)
    assert events == ["library", "playback", "watched", "ratings", "marker"]


def test_unchanged_global_timestamp_skips_bucket_work_and_marker_write():
    latest = activities()
    api = MagicMock()
    api.get_activities.return_value = latest
    service = SimklSyncService(api=api, monitor=MagicMock())

    with patch.object(service, "_get_activities", return_value=latest), patch.object(
        service, "_invalidate"
    ) as invalidate, patch.object(service, "_set_activities") as set_activities:
        assert service.sync_activities() == set()

    invalidate.assert_not_called()
    set_activities.assert_not_called()


def test_changed_buckets_invalidate_only_their_cache_domains_then_persist_marker():
    previous = activities()
    latest = activities(
        "2026-08-05T12:05:00Z",
        values=[
            ("tv_shows", "playback", "2026-08-05T12:04:00Z"),
            ("movies", "completed", "2026-08-05T12:03:00Z"),
            ("anime", "rated_at", "2026-08-05T12:02:00Z"),
        ],
    )
    api = MagicMock()
    api.get_activities.return_value = latest
    service = SimklSyncService(api=api, monitor=MagicMock())

    with patch.object(service, "_get_activities", return_value=previous), patch(
        "lib.services.simkl_sync.invalidate_library_cache"
    ) as library, patch("lib.services.simkl_sync.invalidate_playback_cache") as playback, patch(
        "lib.services.simkl_sync.invalidate_watched_cache"
    ) as watched, patch(
        "lib.services.simkl_sync.invalidate_ratings_cache"
    ) as ratings, patch.object(service, "_set_activities") as set_activities:
        result = service.sync_activities()

    assert result == {"playback", "completed", "rated_at"}
    library.assert_called_once_with()
    playback.assert_called_once_with()
    watched.assert_called_once_with()
    ratings.assert_called_once_with()
    set_activities.assert_called_once_with(latest)


def test_malformed_activity_payload_preserves_prior_marker_and_caches():
    api = MagicMock()
    api.get_activities.return_value = activities(values=[("movies", "completed", "not-a-date")])
    service = SimklSyncService(api=api, monitor=MagicMock())

    with patch.object(service, "_invalidate") as invalidate, patch.object(
        service, "_set_activities"
    ) as set_activities:
        assert service.sync_activities() == set()

    invalidate.assert_not_called()
    set_activities.assert_not_called()


def test_network_failure_preserves_prior_marker_and_caches():
    api = MagicMock()
    api.get_activities.return_value = None
    service = SimklSyncService(api=api, monitor=MagicMock())

    with patch.object(service, "_invalidate") as invalidate, patch.object(
        service, "_set_activities"
    ) as set_activities:
        assert service.sync_activities() == set()

    invalidate.assert_not_called()
    set_activities.assert_not_called()


def test_marker_is_not_advanced_when_invalidation_fails():
    previous = activities()
    latest = activities(
        "2026-08-05T12:05:00Z", values=[("movies", "completed", "2026-08-05T12:03:00Z")]
    )
    api = MagicMock()
    api.get_activities.return_value = latest
    service = SimklSyncService(api=api, monitor=MagicMock())

    with patch.object(service, "_get_activities", return_value=previous), patch.object(
        service, "_invalidate", side_effect=RuntimeError("cache unavailable")
    ), patch.object(service, "_set_activities") as set_activities:
        try:
            service.sync_activities()
        except RuntimeError:
            pass

    set_activities.assert_not_called()


def test_marker_is_persisted_in_its_own_simkl_setting(monkeypatch):
    service = SimklSyncService(api=MagicMock(), monitor=MagicMock())
    stored = {}
    monkeypatch.setattr(
        "lib.services.simkl_sync.get_setting", lambda key, default="": stored.get(key, default)
    )
    monkeypatch.setattr(
        "lib.services.simkl_sync.set_setting", lambda key, value: stored.update({key: value})
    )
    latest = activities()

    service._set_activities(latest)

    assert json.loads(stored["simkl_sync_activities"]) == latest
    assert service._get_activities() == latest


def test_service_waits_in_bounded_steps_and_honors_abort():
    monitor = MagicMock()
    monitor.waitForAbort.side_effect = [False, True]
    service = SimklSyncService(api=MagicMock(), monitor=monitor)

    with patch.object(service, "_get_sync_interval_seconds", return_value=10):
        assert service._wait_for_next_cycle() is True

    assert monitor.waitForAbort.call_args_list[0].args == (5,)
    assert monitor.waitForAbort.call_args_list[1].args == (5,)


def test_service_skips_periodic_work_while_kodi_services_are_paused():
    monitor = MagicMock()
    monitor.abortRequested.side_effect = [False, False, True]
    service = SimklSyncService(api=MagicMock(), monitor=monitor)

    with patch.object(service, "_is_simkl_available", return_value=True), patch.object(
        service, "_wait_for_next_cycle", return_value=False
    ), patch.object(service, "_services_paused", side_effect=[False, True]), patch.object(
        service, "sync_activities"
    ) as sync_activities:
        service.run()

    sync_activities.assert_called_once_with()


def test_service_skips_initial_work_when_kodi_is_already_aborting():
    monitor = MagicMock()
    monitor.abortRequested.return_value = True
    service = SimklSyncService(api=MagicMock(), monitor=monitor)

    with patch.object(service, "_is_simkl_available") as available, patch.object(
        service, "_services_paused"
    ) as paused, patch.object(service, "sync_activities") as sync_activities:
        service.run()

    available.assert_not_called()
    paused.assert_not_called()
    sync_activities.assert_not_called()


def test_service_skips_initial_work_when_kodi_services_are_already_paused():
    monitor = MagicMock()
    monitor.abortRequested.return_value = False
    service = SimklSyncService(api=MagicMock(), monitor=monitor)

    with patch.object(service, "_is_simkl_available", return_value=True), patch.object(
        service, "_services_paused", return_value=True
    ), patch.object(service, "sync_activities") as sync_activities:
        service.run()

    sync_activities.assert_not_called()


def test_service_runs_initial_work_when_authenticated_and_active():
    monitor = MagicMock()
    monitor.abortRequested.side_effect = [False, True]
    service = SimklSyncService(api=MagicMock(), monitor=monitor)

    with patch.object(service, "_is_simkl_available", return_value=True), patch.object(
        service, "_services_paused", return_value=False
    ), patch.object(service, "sync_activities") as sync_activities:
        service.run()

    sync_activities.assert_called_once_with()
