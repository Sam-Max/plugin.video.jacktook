from unittest.mock import MagicMock

import pytest
import xbmc

from lib.utils.player import timing


def test_timing_uses_monotonic_stage_and_total_milliseconds(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(timing, "monotonic", lambda: now[0])
    logger = MagicMock()
    monkeypatch.setattr(timing, "kodilog", logger)
    timer = timing.PlaybackTiming("player")

    now[0] = 101.0
    with timer.stage("trakt"):
        now[0] = 103.5
    now[0] = 104.0
    timer.mark("kodi_wait_begin")
    now[0] = 114.0
    timer.mark("kodi_playing")
    timer.finish("playing")
    timer.finish("not_started")

    lines = [item.args[0] for item in logger.call_args_list]
    assert len(lines) == 4
    assert "stage=trakt elapsed_ms=2500 total_ms=3500 outcome=ok" in lines[0]
    assert "stage=kodi_playing elapsed_ms=10000 total_ms=14000" in lines[2]
    assert "stage=startup_total elapsed_ms=14000 total_ms=14000 outcome=playing" in lines[3]
    assert all(item.kwargs["level"] == xbmc.LOGINFO for item in logger.call_args_list)


def test_failed_stage_logs_duration_but_not_exception_details(monkeypatch):
    logger = MagicMock()
    monkeypatch.setattr(timing, "kodilog", logger)
    timer = timing.PlaybackTiming("torbox")

    with pytest.raises(RuntimeError, match="secret-token"):
        with timer.stage("torbox_download_link"):
            raise RuntimeError("https://private.invalid/?token=secret-token")

    message = logger.call_args.args[0]
    assert "outcome=error" in message
    assert "private.invalid" not in message
    assert "secret-token" not in message


def test_logging_failure_does_not_interrupt_body_or_replace_original_error(monkeypatch):
    monkeypatch.setattr(timing, "kodilog", MagicMock(side_effect=OSError("logging unavailable")))
    timer = timing.PlaybackTiming("player")
    operations = []
    with timer.stage("trakt"):
        operations.append("completed")
    assert operations == ["completed"]
    with pytest.raises(ValueError, match="original failure"):
        with timer.stage("subtitles"):
            raise ValueError("original failure")
    timer.finish("error")
    assert timer.finished is True
