from contextlib import contextmanager, suppress
from time import monotonic
from uuid import uuid4

import xbmc

from lib.utils.kodi.logging import kodilog


class PlaybackTiming:
    """Log fixed diagnostic stages without media or account identifiers."""

    def __init__(self, component):
        self.component = component
        self.trace = uuid4().hex[:8]
        self.started_at = monotonic()
        self.previous_at = self.started_at
        self.finished = False

    def mark(self, stage, started_at=None, outcome="ok"):
        now = monotonic()
        elapsed_ms = int((now - (self.previous_at if started_at is None else started_at)) * 1000)
        total_ms = int((now - self.started_at) * 1000)
        self.previous_at = now
        # Diagnostics must never interrupt playback or mask its original error.
        with suppress(Exception):
            kodilog(
                f"[PLAYBACK-TIMING] trace={self.trace} component={self.component} "
                f"stage={stage} elapsed_ms={elapsed_ms} total_ms={total_ms} outcome={outcome}",
                level=xbmc.LOGINFO,
            )

    @contextmanager
    def stage(self, name):
        started_at = monotonic()
        outcome = "ok"
        try:
            yield
        except Exception:
            outcome = "error"
            raise
        finally:
            self.mark(name, started_at, outcome)

    def finish(self, outcome):
        if not self.finished:
            self.mark("startup_total", self.started_at, outcome)
            self.finished = True
