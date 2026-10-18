"""On-screen bitrate info shown over the fullscreen video while playback is paused.

Kodi exposes no video bitrate to add-ons, so the average bitrate is derived from the
file size and the total duration. Labels are added straight to the fullscreen video
window instead of a dialog, so they never take focus or swallow remote keys.
"""

import os
from json import dumps, loads
from typing import Any, Dict, List, Optional, Tuple

from lib.utils.kodi.logging import kodilog
from lib.utils.kodi.utils import ADDON_PATH, translation

import xbmc
import xbmcgui
import xbmcvfs

FULLSCREEN_VIDEO_WINDOW_ID = 12005
BACKGROUND_TEXTURE = os.path.join(ADDON_PATH, "resources", "skins", "Default", "media", "white.png")


def average_bitrate(size_bytes: Any, duration_seconds: Any) -> int:
    """Return the average bitrate in bits per second, or 0 when it can't be computed."""
    try:
        size = int(size_bytes)
        duration = float(duration_seconds)
    except (TypeError, ValueError):
        return 0
    if size <= 0 or duration <= 0:
        return 0
    return int(size * 8 / duration)


def format_bitrate(bits_per_second: Any) -> str:
    try:
        value = float(bits_per_second)
    except (TypeError, ValueError):
        return ""
    if value <= 0:
        return ""
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f} Mbps"
    return f"{value / 1000:.0f} kbps"


def format_stream_details(video: Optional[Dict], audio: Optional[Dict]) -> str:
    parts: List[str] = []
    video = video or {}
    audio = audio or {}

    width, height = video.get("width") or 0, video.get("height") or 0
    if width and height:
        parts.append(f"{width}x{height}")
    if video.get("codec"):
        parts.append(str(video["codec"]).upper())

    audio_parts = []
    if audio.get("codec"):
        audio_parts.append(str(audio["codec"]).upper())
    if audio.get("channels"):
        audio_parts.append(f"{audio['channels']}ch")
    audio_bitrate = format_bitrate(audio.get("bitrate"))
    if audio_bitrate:
        audio_parts.append(audio_bitrate)
    if audio_parts:
        parts.append(f"{translation(91074)}: {' '.join(audio_parts)}")

    return " · ".join(parts)


def build_overlay_lines(
    size_bytes: Any, duration_seconds: Any, video: Optional[Dict], audio: Optional[Dict]
) -> Tuple[str, str]:
    bitrate = format_bitrate(average_bitrate(size_bytes, duration_seconds))
    title = f"{translation(91073)}: ~{bitrate}" if bitrate else ""
    return title, format_stream_details(video, audio)


def get_file_size(path: str) -> int:
    """Size of the playing file; Kodi stats HTTP streams (debrid, TorrServer) via HEAD/range."""
    if not path or path.startswith("plugin://"):
        return 0
    handle = None
    try:
        handle = xbmcvfs.File(path)
        return int(handle.size() or 0)
    except Exception as e:
        kodilog(f"Pause overlay: could not read file size: {e}")
        return 0
    finally:
        if handle is not None:
            handle.close()


def get_current_streams() -> Tuple[Dict, Dict]:
    try:
        players = loads(
            xbmc.executeJSONRPC(dumps({"jsonrpc": "2.0", "method": "Player.GetActivePlayers", "id": 1}))
        ).get("result") or []
        player_id = next((p.get("playerid") for p in players if p.get("type") == "video"), None)
        if player_id is None:
            return {}, {}
        result = loads(
            xbmc.executeJSONRPC(
                dumps(
                    {
                        "jsonrpc": "2.0",
                        "method": "Player.GetProperties",
                        "params": {
                            "playerid": player_id,
                            "properties": ["currentvideostream", "currentaudiostream"],
                        },
                        "id": 1,
                    }
                )
            )
        ).get("result", {})
        return result.get("currentvideostream") or {}, result.get("currentaudiostream") or {}
    except Exception as e:
        kodilog(f"Pause overlay: could not read stream details: {e}")
        return {}, {}


class PauseInfoOverlay:
    def __init__(self) -> None:
        self._window: Optional[xbmcgui.Window] = None
        self._controls: List[xbmcgui.Control] = []

    @property
    def visible(self) -> bool:
        return bool(self._controls)

    def show(self, title: str, details: str) -> None:
        if self._controls or not (title or details):
            return
        try:
            window = xbmcgui.Window(FULLSCREEN_VIDEO_WINDOW_ID)
            # Controls use the skin's coordinate space (1920x1080 or 1280x720).
            scale = (window.getHeight() or 1080) / 1080
            width, line_height, margin = int(760 * scale), int(44 * scale), int(40 * scale)
            lines = [line for line in (title, details) if line]
            height = line_height * len(lines) + int(24 * scale)
            x = (window.getWidth() or 1920) - width - margin
            y = int(150 * scale)

            controls: List[xbmcgui.Control] = [
                xbmcgui.ControlImage(x, y, width, height, BACKGROUND_TEXTURE, colorDiffuse="0xB0000000")
            ]
            for index, line in enumerate(lines):
                controls.append(
                    xbmcgui.ControlLabel(
                        x + int(20 * scale),
                        y + int(12 * scale) + index * line_height,
                        width - int(40 * scale),
                        line_height,
                        line,
                        font="font13" if index == 0 else "font12",
                        textColor="0xFFFFFFFF" if index == 0 else "0xFFCCCCCC",
                        alignment=0x00000001,  # XBFONT_RIGHT
                    )
                )
            window.addControls(controls)
            self._window, self._controls = window, controls
        except Exception as e:
            kodilog(f"Pause overlay: could not show: {e}")
            self._window, self._controls = None, []

    def hide(self) -> None:
        if not self._controls:
            return
        try:
            if self._window is not None:
                self._window.removeControls(self._controls)
        except Exception as e:
            kodilog(f"Pause overlay: could not hide: {e}")
        finally:
            self._window, self._controls = None, []
