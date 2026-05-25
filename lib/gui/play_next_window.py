import xbmc

from lib.gui.play_window import PlayWindow
from lib.utils.kodi.utils import get_setting, kodilog


def _safe_text(value):
    if value is None:
        return ""
    return str(value)


def _safe_int(value):
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _dict_value(data, *keys):
    if not isinstance(data, dict):
        return ""
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return ""


def build_next_episode_properties(item_information):
    item_information = item_information or {}
    tv_data = item_information.get("tv_data") or {}
    next_tv_data = item_information.get("next_tv_data") or {}

    if not isinstance(tv_data, dict):
        tv_data = {}
    if not isinstance(next_tv_data, dict):
        next_tv_data = {}

    season = _safe_int(next_tv_data.get("season"))
    episode = _safe_int(next_tv_data.get("episode"))

    if season is None:
        season = _safe_int(tv_data.get("season"))

    if episode is None:
        current_episode = _safe_int(tv_data.get("episode"))
        if current_episode is not None:
            episode = current_episode + 1

    if season is not None and episode is not None:
        episode_label = f"S{season:02d}E{episode:02d}"
    elif episode is not None:
        episode_label = f"Episode {episode}"
    else:
        episode_label = ""

    episode_name = _safe_text(_dict_value(next_tv_data, "name", "title", "episode_name"))
    if not episode_name and episode is not None:
        episode_name = f"Episode {episode}"

    title = _safe_text(
        _dict_value(
            item_information,
            "show_title",
            "tvshowtitle",
            "series_title",
            "query",
            "title",
            "next_label",
        )
    )

    return {
        "next.title": title,
        "next.poster": _safe_text(_dict_value(item_information, "poster", "thumb", "icon")),
        "next.fanart": _safe_text(_dict_value(item_information, "fanart", "backdrop")),
        "next.clearlogo": _safe_text(_dict_value(item_information, "clearlogo")),
        "next.season": "" if season is None else str(season),
        "next.episode": "" if episode is None else str(episode),
        "next.episode_label": episode_label,
        "next.episode_name": episode_name,
        "next.plot": _safe_text(_dict_value(item_information, "plot", "overview")),
    }


class PlayNext(PlayWindow):
    def __init__(self, xml_file, xml_location, item_information=None):
        super().__init__(xml_file, xml_location, item_information=item_information)
        self.default_action = 2
        self.auto_timeout = int(get_setting("playnext_auto_timeout", "10"))
        self._set_next_episode_properties(item_information or {})

    def _set_next_episode_properties(self, item_information):
        for key, value in build_next_episode_properties(item_information).items():
            self.setProperty(key, value)

    def background_tasks(self):
        if self.auto_timeout <= 0:
            # Legacy mode: episode-remaining timer, respects global auto_play
            self.setProperty("timer_label", "Playing in {} seconds")
            super().background_tasks()
            return

        # Auto-timeout mode: count down from setting, independent of auto_play
        try:
            try:
                progress_bar = self.getControl(3014)
                if not hasattr(progress_bar, "setPercent"):
                    progress_bar = None
            except (RuntimeError, AttributeError):
                progress_bar = None

            # Snapshot episode remaining for progress bar scaling
            episode_remaining = max(int(self.getTotalTime()) - int(self.getTime()), 1)
            self.duration = episode_remaining

            remaining = self.auto_timeout
            ticks = 0

            while remaining > 0 and not self.closed and self.playing_file == self.getPlayingFile():
                episode_left = int(self.getTotalTime()) - int(self.getTime())

                # Episode ended (2s or less) -> auto-play immediately
                if episode_left <= 2:
                    self.handle_action(7, 3001)
                    return

                # Decrement displayed timeout every 2 ticks (= 1 real second)
                if ticks > 0 and ticks % 2 == 0:
                    remaining -= 1

                self.setProperty("timer", str(remaining))
                self.setProperty(
                    "timer_label",
                    f"Auto-playing in {remaining} seconds",
                )

                if progress_bar is not None:
                    progress_bar.setPercent(self.calculate_percent())

                xbmc.sleep(500)
                ticks += 1

            # Timeout reached — auto-play
            if not self.closed and self.playing_file == self.getPlayingFile():
                self.handle_action(7, 3001)

        except Exception as e:
            kodilog(f"Error in auto-timeout background_tasks: {e}")

        self.close()

    def smart_play_action(self):
        if get_setting("auto_play"):
            self.handle_action(7, 3001)
            return

        if (
            self.default_action == 1
            and self.playing_file == self.getPlayingFile()
            and not self.closed
        ):
            self.pause()
