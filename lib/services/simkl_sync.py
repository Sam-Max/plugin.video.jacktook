import json

import xbmc

from lib.api.simkl import SimklClient, is_simkl_authenticated
from lib.api.simkl_cache import (
    invalidate_library_cache,
    invalidate_playback_cache,
    invalidate_ratings_cache,
    invalidate_watched_cache,
)
from lib.utils.kodi.utils import get_property_no_fallback, get_setting, kodilog, set_setting

PAUSE_SERVICES_PROP = "jacktook.pause_services"
ACTIVITIES_SETTING = "simkl_sync_activities"
DEFAULT_SYNC_INTERVAL_MINUTES = 15
WAIT_STEP_SECONDS = 5
DOMAIN_BUCKETS = (
    "rated_at",
    "playback",
    "plantowatch",
    "watching",
    "completed",
    "hold",
    "dropped",
    "removed_from_list",
)
LIST_BUCKETS = frozenset(DOMAIN_BUCKETS) - {"rated_at", "playback"}


class SimklSyncService:
    def __init__(self, api=None, monitor=None):
        self.api = api or SimklClient()
        self.monitor = monitor or xbmc.Monitor()

    def run(self):
        if self.monitor.abortRequested():
            return
        if not self._is_simkl_available():
            return
        if self._services_paused():
            return
        try:
            self._sync_safely()
            while not self.monitor.abortRequested():
                if self._wait_for_next_cycle():
                    return
                if self._is_simkl_available() and not self._services_paused():
                    self._sync_safely()
        except Exception as error:
            kodilog(f"[SIMKL] activity sync failed ({type(error).__name__})", level=xbmc.LOGERROR)

    def _sync_safely(self):
        try:
            self.sync_activities()
        except Exception as error:
            kodilog(f"[SIMKL] activity sync failed ({type(error).__name__})", level=xbmc.LOGERROR)

    def _is_simkl_available(self):
        return is_simkl_authenticated()

    def _services_paused(self):
        return get_property_no_fallback(PAUSE_SERVICES_PROP) == "true"

    def _get_sync_interval_seconds(self):
        try:
            interval = int(get_setting("simkl_sync_interval", DEFAULT_SYNC_INTERVAL_MINUTES))
        except (TypeError, ValueError):
            interval = DEFAULT_SYNC_INTERVAL_MINUTES
        return max(interval, 1) * 60

    def _wait_for_next_cycle(self):
        remaining = self._get_sync_interval_seconds()
        while remaining > 0:
            if self.monitor.waitForAbort(min(WAIT_STEP_SECONDS, remaining)):
                return True
            remaining -= WAIT_STEP_SECONDS
        return False

    @staticmethod
    def _timestamp(value):
        return value if SimklClient._is_iso8601_timestamp(value) else None

    def _get_activities(self):
        value = get_setting(ACTIVITIES_SETTING, "")
        if not isinstance(value, str) or not value:
            return None
        try:
            activities = json.loads(value)
        except (TypeError, ValueError):
            return None
        return activities if isinstance(activities, dict) else None

    def _set_activities(self, activities):
        set_setting(ACTIVITIES_SETTING, json.dumps(activities, sort_keys=True))

    def _validated_activities(self, activities):
        if not isinstance(activities, dict) or not self._timestamp(activities.get("all")):
            return None
        normalized = {"all": activities["all"]}
        settings = activities.get("settings", {})
        if settings is None:
            settings = {}
        if not isinstance(settings, dict):
            return None
        settings_all = settings.get("all")
        if settings_all is not None:
            settings_all = self._timestamp(settings_all)
            if settings_all is None:
                return None
            normalized["settings"] = {"all": settings_all}
        for domain in ("tv_shows", "movies", "anime"):
            values = activities.get(domain, {})
            if values is None:
                values = {}
            if not isinstance(values, dict):
                return None
            domain_values = {}
            for bucket in DOMAIN_BUCKETS:
                if bucket not in values or values[bucket] is None:
                    continue
                timestamp = self._timestamp(values[bucket])
                if timestamp is None:
                    return None
                domain_values[bucket] = timestamp
            normalized[domain] = domain_values
        return normalized

    def _changed_buckets(self, previous, latest):
        changes = set()
        for domain in ("tv_shows", "movies", "anime"):
            previous_domain = previous.get(domain, {})
            latest_domain = latest.get(domain, {})
            for bucket, timestamp in latest_domain.items():
                if previous_domain.get(bucket) != timestamp:
                    changes.add(bucket)
        return changes

    def _invalidate(self, changes, baseline=False):
        if baseline or changes & LIST_BUCKETS:
            invalidate_library_cache()
        if baseline or "playback" in changes:
            invalidate_playback_cache()
        if baseline or changes:
            invalidate_watched_cache()
        if baseline or "rated_at" in changes:
            invalidate_ratings_cache()

    def sync_activities(self):
        latest = self._validated_activities(self.api.get_activities())
        if latest is None:
            return set()
        previous = self._get_activities()
        if previous is None:
            self._invalidate(set(), baseline=True)
            self._set_activities(latest)
            return set(DOMAIN_BUCKETS)
        if previous.get("all") == latest["all"]:
            return set()
        changes = self._changed_buckets(previous, latest)
        self._invalidate(changes)
        self._set_activities(latest)
        return changes
