from unittest.mock import MagicMock, patch

import pytest

from lib.gui import pause_info_overlay as overlay
from lib.gui.pause_info_overlay import (
    average_bitrate,
    build_overlay_lines,
    format_bitrate,
    format_stream_details,
)


@pytest.fixture(autouse=True)
def _labels():
    labels = {91073: "Bitrate", 91074: "Audio"}
    with patch.object(overlay, "translation", side_effect=labels.get):
        yield


@pytest.mark.parametrize(
    "size,duration,expected",
    [
        (9_000_000_000, 7200, 10_000_000),
        (0, 7200, 0),
        (9_000_000_000, 0, 0),
        (None, 7200, 0),
        ("1000", "8", 1000),
    ],
)
def test_average_bitrate(size, duration, expected):
    assert average_bitrate(size, duration) == expected


@pytest.mark.parametrize(
    "value,expected",
    [(12_400_000, "12.4 Mbps"), (640_000, "640 kbps"), (0, ""), (None, "")],
)
def test_format_bitrate(value, expected):
    assert format_bitrate(value) == expected


def test_format_stream_details_combines_video_and_audio():
    details = format_stream_details(
        {"width": 1920, "height": 1080, "codec": "hevc"},
        {"codec": "eac3", "channels": 6, "bitrate": 640_000},
    )

    assert details == "1920x1080 · HEVC · Audio: EAC3 6ch 640 kbps"


def test_build_overlay_lines_without_size_keeps_only_stream_details():
    title, details = build_overlay_lines(0, 7200, {"width": 1280, "height": 720}, {})

    assert title == ""
    assert details == "1280x720"


def test_build_overlay_lines_with_size():
    title, _ = build_overlay_lines(9_000_000_000, 7200, {}, {})

    assert title == "Bitrate: ~10.0 Mbps"


@pytest.mark.parametrize("path", ["", "plugin://plugin.video.elementum/play"])
def test_get_file_size_skips_unsupported_paths(path):
    with patch.object(overlay.xbmcvfs, "File") as file_cls:
        assert overlay.get_file_size(path) == 0
    file_cls.assert_not_called()


def test_overlay_show_and_hide_add_and_remove_controls():
    window = MagicMock()
    window.getWidth.return_value = 1920
    window.getHeight.return_value = 1080
    with patch.object(overlay.xbmcgui, "Window", return_value=window):
        pause_overlay = overlay.PauseInfoOverlay()
        pause_overlay.show("Bitrate: ~10.0 Mbps", "1920x1080")
        pause_overlay.show("Bitrate: ~10.0 Mbps", "1920x1080")

    window.addControls.assert_called_once()
    assert len(window.addControls.call_args.args[0]) == 3
    assert pause_overlay.visible

    pause_overlay.hide()

    window.removeControls.assert_called_once()
    assert not pause_overlay.visible


def test_overlay_show_ignores_empty_lines():
    with patch.object(overlay.xbmcgui, "Window") as window_cls:
        overlay.PauseInfoOverlay().show("", "")

    window_cls.assert_not_called()
