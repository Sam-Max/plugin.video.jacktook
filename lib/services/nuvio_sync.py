"""Background mirror sync for the Nuvio profile library.

The service bootstraps once per profile in the documented order — capture the
delta cursor, page the full snapshot, then replay deltas since that cursor — and
then polls deltas on an interval. It only ever calls read-only RPCs and writes
to the local SQLite mirror via ``NuvioStore``.
"""

import threading
from time import monotonic

import xbmc

from lib.api.nuvio import NuvioClient, is_nuvio_progress_sync_enabled
from lib.api.nuvio_store import (
    UI_READ_TIMEOUT_SECONDS,
    NuvioStore,
    invalidate_nuvio_library_cache,
)
from lib.utils.kodi.utils import get_property_no_fallback, get_setting, kodilog

PAUSE_SERVICES_PROP = "jacktook.pause_services"
DEFAULT_SYNC_INTERVAL_MINUTES = 15
WAIT_STEP_SECONDS = 5
SNAPSHOT_PAGE_LIMIT = 500
DELTA_PAGE_LIMIT = 1000

# Opening the offline library view triggers one best-effort delta sync so recent
# web-side changes appear without waiting for the next background cycle. The
# sync runs on a worker thread and the view waits at most the budget for it, so
# a blocking RPC or database lock can never hold the UI thread past the budget;
# the worker is abandoned and its cooperative deadline stops it promptly. The
# debounce avoids re-syncing on immediate re-renders.
VIEW_SYNC_DEBOUNCE_SECONDS = 15.0
VIEW_SYNC_BUDGET_SECONDS = 4.0
# Per-request cap for the view-sync client. Each request is additionally clamped
# to the remaining budget, so no single RPC can outlast the deadline.
VIEW_SYNC_REQUEST_TIMEOUT_SECONDS = 2.0


def _deadline_passed(deadline):
    """True when an optional monotonic deadline has elapsed."""
    return deadline is not None and monotonic() >= deadline


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

    def _bootstrap_if_needed(self, deadline=None):
        """Snapshot once, then fall through to delta; retry when not ready.

        The session is reloaded from settings first so the service follows the
        currently selected profile and credentials across login, logout, token
        refresh, and profile switches without a restart. The cursor is captured
        before the first snapshot page so changes made during the snapshot are
        replayed by the delta that follows. A failed cursor or snapshot page
        leaves ``snapshot_done`` at 0 for the next cycle.
        """
        if _deadline_passed(deadline):
            return
        self._reload_session()
        profile_id = self._profile_id()
        if profile_id is None:
            return
        if _deadline_passed(deadline):
            return
        meta = self.store.get_meta(profile_id)
        if meta is None:
            return
        if meta.get("snapshot_done"):
            self._delta_once(deadline=deadline)
            return
        if _deadline_passed(deadline):
            return
        cursor = self.api.get_library_delta_cursor()
        if cursor is None:
            return
        if _deadline_passed(deadline):
            return
        if not self.store.begin_snapshot(profile_id):
            return
        offset = 0
        while True:
            if _deadline_passed(deadline):
                return
            page = self.api.get_library_page(limit=SNAPSHOT_PAGE_LIMIT, offset=offset)
            if page is None:
                return
            items, raw_count = page
            if items and not self.store.write_snapshot_items(profile_id, items):
                return
            if raw_count < SNAPSHOT_PAGE_LIMIT:
                break
            offset += SNAPSHOT_PAGE_LIMIT
        if not self.store.finish_snapshot(profile_id, cursor):
            return
        self._delta_once(deadline=deadline)

    def _delta_once(self, deadline=None):
        """Apply every delta page since the stored cursor in ascending order."""
        profile_id = self._profile_id()
        if profile_id is None:
            return
        changed = False
        if _deadline_passed(deadline):
            return
        since = self.store.get_cursor_event_id(profile_id)
        while True:
            if _deadline_passed(deadline):
                return
            page = self.api.get_library_delta_page(since_event_id=since, limit=DELTA_PAGE_LIMIT)
            if page is None:
                return
            events, raw_count = page
            if not events:
                break
            max_event_id = max(event["event_id"] for event in events)
            if not self.store.apply_delta(profile_id, events, max_event_id):
                return
            changed = True
            since = max_event_id
            if raw_count < DELTA_PAGE_LIMIT:
                break
        if changed:
            invalidate_nuvio_library_cache()

    def _is_nuvio_available(self):
        return is_nuvio_progress_sync_enabled()

    def _reload_session(self):
        """Re-read the live session so a long-lived client follows settings.

        Injection-safe: clients that do not expose ``reload_session`` (test
        doubles) are left untouched.
        """
        reload_session = getattr(self.api, "reload_session", None)
        if callable(reload_session):
            reload_session()

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


_LAST_VIEW_SYNC_AT = 0.0
_VIEW_SYNC_LOCK = threading.Lock()
_VIEW_SYNC_THREAD = None


def _run_view_sync(started_at, budget, outcome):
    """Best-effort sync executed off the UI thread with a cooperative deadline.

    ``outcome`` is a one-element dict shared with the caller: it reports whether
    the sync actually completed, so a swallowed failure is not mistaken for a
    successful run.
    """
    global _VIEW_SYNC_THREAD
    store = None
    try:
        deadline = started_at + budget
        store = NuvioStore(timeout=UI_READ_TIMEOUT_SECONDS)
        api = NuvioClient(
            request_timeout=VIEW_SYNC_REQUEST_TIMEOUT_SECONDS,
            deadline=deadline,
        )
        NuvioSyncService(api=api, store=store)._bootstrap_if_needed(deadline=deadline)
        outcome["ok"] = True
    except Exception as error:
        kodilog(f"[NUVIO] view sync failed ({type(error).__name__})")
    finally:
        if store is not None:
            store.close()
        with _VIEW_SYNC_LOCK:
            _VIEW_SYNC_THREAD = None


def sync_library_if_stale(
    max_age_seconds=VIEW_SYNC_DEBOUNCE_SECONDS,
    max_seconds=VIEW_SYNC_BUDGET_SECONDS,
):
    """Run one best-effort delta sync before rendering the library view.

    The background service polls on an interval, so a change made on the Nuvio
    website can take minutes to reach the local mirror. Opening the library view
    calls this first so the render reflects those changes. The sync runs on a
    worker thread and this call waits at most ``max_seconds`` for it, so a
    blocking RPC or database lock cannot hold the UI thread past the budget; a
    slow sync is abandoned and the existing mirror still renders. It never
    raises.

    Returns True when a sync ran and succeeded within the budget, False when it
    was skipped (disabled, no profile, inside the debounce window, already
    running), failed, or did not finish in time.
    """
    global _LAST_VIEW_SYNC_AT, _VIEW_SYNC_THREAD
    if not is_nuvio_progress_sync_enabled():
        return False
    if NuvioClient._profile_index(get_setting("nuvio_profile_id")) is None:
        return False
    now = monotonic()
    budget = max(0.0, max_seconds)
    outcome = {"ok": False}
    with _VIEW_SYNC_LOCK:
        if now - _LAST_VIEW_SYNC_AT < max_age_seconds:
            return False
        if _VIEW_SYNC_THREAD is not None and _VIEW_SYNC_THREAD.is_alive():
            return False
        _LAST_VIEW_SYNC_AT = now
        worker = threading.Thread(
            target=_run_view_sync,
            args=(now, budget, outcome),
            name="jacktook-nuvio-view-sync",
            daemon=True,
        )
        _VIEW_SYNC_THREAD = worker
        worker.start()
    worker.join(budget)
    return outcome["ok"]
