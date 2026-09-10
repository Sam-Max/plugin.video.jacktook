"""Background mirror sync for the Nuvio profile library.

The service bootstraps once per profile in the documented order — capture the
delta cursor, page the full snapshot, then replay deltas since that cursor — and
then polls deltas on an interval. It only ever calls read-only RPCs and writes
to the local SQLite mirror via ``NuvioStore``.
"""

import xbmc

from lib.api.nuvio import NuvioClient, is_nuvio_progress_sync_enabled
from lib.api.nuvio_store import NuvioStore, invalidate_nuvio_library_cache
from lib.utils.kodi.utils import get_property_no_fallback, get_setting, kodilog

PAUSE_SERVICES_PROP = "jacktook.pause_services"
DEFAULT_SYNC_INTERVAL_MINUTES = 15
WAIT_STEP_SECONDS = 5
SNAPSHOT_PAGE_LIMIT = 500
DELTA_PAGE_LIMIT = 1000


class NuvioSyncService:
    """Mirror the Nuvio profile library into SQLite on a background thread."""

    def __init__(self, api=None, monitor=None, store=None):
        self.api = api or NuvioClient()
        self.monitor = monitor or xbmc.Monitor()
        self.store = store or NuvioStore()

    def run(self):
        if self.monitor.abortRequested():
            return
        if not self._is_nuvio_available():
            return
        if self._services_paused():
            return
        try:
            self._bootstrap_if_needed()
            while not self.monitor.abortRequested():
                if self._wait_for_next_cycle():
                    return
                if not self._is_nuvio_available() or self._services_paused():
                    continue
                self._sync_safely()
        except Exception as error:
            kodilog(f"[NUVIO] library sync failed ({type(error).__name__})", level=xbmc.LOGERROR)

    def _sync_safely(self):
        try:
            self._bootstrap_if_needed()
        except Exception as error:
            kodilog(f"[NUVIO] library sync failed ({type(error).__name__})", level=xbmc.LOGERROR)

    def _bootstrap_if_needed(self):
        """Snapshot once, then fall through to delta; retry when not ready.

        The cursor is captured before the first snapshot page so changes made
        during the snapshot are replayed by the delta that follows. A failed
        cursor or snapshot page leaves ``snapshot_done`` at 0 for the next cycle.
        """
        profile_id = self._profile_id()
        if profile_id is None:
            return
        meta = self.store.get_meta(profile_id)
        if meta is None:
            return
        if meta.get("snapshot_done"):
            self._delta_once()
            return
        cursor = self.api.get_library_delta_cursor()
        if cursor is None:
            return
        if not self.store.begin_snapshot(profile_id):
            return
        offset = 0
        while True:
            page = self.api.get_library(limit=SNAPSHOT_PAGE_LIMIT, offset=offset)
            if page is None:
                return
            if page and not self.store.write_snapshot_items(profile_id, page):
                return
            if len(page) < SNAPSHOT_PAGE_LIMIT:
                break
            offset += SNAPSHOT_PAGE_LIMIT
        if not self.store.finish_snapshot(profile_id, cursor):
            return
        self._delta_once()

    def _delta_once(self):
        """Apply every delta page since the stored cursor in ascending order."""
        profile_id = self._profile_id()
        if profile_id is None:
            return
        changed = False
        since = self.store.get_cursor_event_id(profile_id)
        while True:
            events = self.api.get_library_delta(since_event_id=since, limit=DELTA_PAGE_LIMIT)
            if events is None:
                return
            if not events:
                break
            max_event_id = max(event["event_id"] for event in events)
            if not self.store.apply_delta(profile_id, events, max_event_id):
                return
            changed = True
            since = max_event_id
            if len(events) < DELTA_PAGE_LIMIT:
                break
        if changed:
            invalidate_nuvio_library_cache()

    def _is_nuvio_available(self):
        return is_nuvio_progress_sync_enabled()

    def _services_paused(self):
        return get_property_no_fallback(PAUSE_SERVICES_PROP) == "true"

    def _profile_id(self):
        return NuvioClient._profile_index(getattr(self.api, "profile_id", None))

    def _get_sync_interval_seconds(self):
        try:
            interval = int(get_setting("nuvio_sync_interval", DEFAULT_SYNC_INTERVAL_MINUTES))
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
