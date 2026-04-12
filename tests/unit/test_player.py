from pathlib import Path
import re


PLAYER_PATH = Path(__file__).resolve().parents[2] / "lib" / "player.py"


def test_monitor_finally_uses_non_destructive_cleanup():
    source = PLAYER_PATH.read_text()
    monitor_match = re.search(r"def monitor\(self\):(?P<body>.*?)def handle_subtitles", source, re.S)

    assert monitor_match is not None

    monitor_body = monitor_match.group("body")
    finally_match = re.search(r"finally:\n(?P<body>(?:\s+.*\n)+)", monitor_body)

    assert finally_match is not None

    finally_body = finally_match.group("body")
    assert "self._cleanup_playback_session()" in finally_body
    assert "self.cancel_playback()" not in finally_body


def test_cancel_playback_still_invalidates_resolved_url():
    source = PLAYER_PATH.read_text()
    cancel_match = re.search(
        r"def cancel_playback\(self\):(?P<body>.*?)def _cleanup_playback_session",
        source,
        re.S,
    )

    assert cancel_match is not None

    cancel_body = cancel_match.group("body")
    assert "self._cleanup_playback_session()" in cancel_body
    assert "setResolvedUrl(ADDON_HANDLE, False, ListItem(offscreen=True))" in cancel_body
