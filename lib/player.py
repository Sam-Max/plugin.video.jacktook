from json import dumps as json_dumps
import traceback
from lib.api.trakt.trakt_utils import is_trakt_auth
from lib.clients.tmdb.utils import tmdb_get
from lib.api.trakt.trakt import TraktAPI, TraktLists
from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    PLAYLIST,
    action_url_run,
    build_url,
    clear_property,
    close_all_dialog,
    close_busy_dialog,
    execute_builtin,
    get_setting,
    kodilog,
    notification,
    set_property,
    sleep,
)
from lib.utils.general.utils import (
    make_listing,
    set_watched_file,
)

import xbmc
from xbmc import getCondVisibility as get_visibility
from xbmcgui import ListItem
from xbmcplugin import setResolvedUrl


total_time_errors = ("0.0", "", 0.0, None)
set_resume, set_watched = 5, 90
video_fullscreen_check = "Window.IsActive(fullscreenvideo)"


class JacktookPLayer(xbmc.Player):
    def __init__(self):
        xbmc.Player.__init__(self)
        self.url = None
        self.kodi_monitor = None
        self.playback_percent = 0.0
        self.playing_filename = ""
        self.media_marked = False
        self.playback_successful = None
        self.cancel_all_playback = False
        self.next_dialog = get_setting("playnext_dialog_enabled")
        self.playing_next_time = int(get_setting("playnext_time"))
        self.PLAYLIST = PLAYLIST

    def run(self, data=None):
        self.set_constants(data)
        self.clear_playback_properties()
        self.add_external_trakt_scrolling()
        self.mark_watched(data)

        close_busy_dialog()

        try:
            list_item = make_listing(data)
            self.PLAYLIST.add(self.url, list_item)
            if self.data["mode"] == "tv":
                self.build_playlist()
            self.play_video(list_item)
        except Exception as e:
            kodilog(traceback.print_exc())
            kodilog(f"Error in run: {e}")
            self.run_error()

    def play_playlist(self):
        close_busy_dialog()
        try:
            self.play(self.PLAYLIST)
            self.check_playback_start()

            if self.playback_successful:
                self.monitor()
            else:
                if self.cancel_all_playback:
                    self.kill_dialog()
                self.stop()

        except Exception as e:
            notification(f"Error playing playlist: {e}")
            self.run_error()

    def play_video(self, list_item):
        close_busy_dialog()

        try:
            if (
                is_trakt_auth()
                and get_setting("trakt_scrobbling_enabled")
                and self.data.get("ids")
            ):
                last_position = TraktAPI().scrobble.trakt_get_last_tracked_position(
                    self.data
                )
                if last_position > 0:
                    list_item.setProperty("StartPercent", str(last_position))
                TraktAPI().scrobble.trakt_start_scrobble(self.data)

            setResolvedUrl(ADDON_HANDLE, True, list_item)
            self.check_playback_start()

            if self.playback_successful:
                self.monitor()
            else:
                if self.cancel_all_playback:
                    self.kill_dialog()
                self.stop()

        except Exception as e:
            kodilog(f"Error during playback: {e}")
            kodilog(traceback.format_exc())
            self.run_error()
        finally:
            try:
                del self.kodi_monitor
            except:
                pass

    def check_playback_start(self):
        resolve_percent = 0

        while self.playback_successful is None:
            if self.kodi_monitor.abortRequested():
                self.cancel_all_playback = True
                self.playback_successful = False
            elif resolve_percent >= 100:
                self.playback_successful = False
            elif get_visibility("Window.IsTopMost(okdialog)"):
                execute_builtin("SendClick(okdialog, 11)")
                self.playback_successful = False
            elif self.isPlayingVideo():
                try:
                    if self.getTotalTime() not in total_time_errors and get_visibility(
                        video_fullscreen_check
                    ):
                        self.playback_successful = True

                        break
                except Exception as e:
                    kodilog(f"Error in check_playback_start: {e}")

            resolve_percent = round(resolve_percent + 26.0 / 100, 1)
            sleep(50)

    def monitor(self):
        ensure_dialog_dead = False
        total_check_time = 0

        try:
            while total_check_time <= 30 and not get_visibility(video_fullscreen_check):
                sleep(100)
                total_check_time += 0.10

            close_busy_dialog()
            sleep(1000)

            while self.isPlayingVideo():
                try:
                    self.total_time, self.current_time = (
                        self.getTotalTime(),
                        self.getTime(),
                    )

                    if not ensure_dialog_dead:
                        ensure_dialog_dead = True
                        self.playback_close_dialogs()

                    sleep(1000)

                    self.watched_percentage = round(
                        float(self.current_time / self.total_time * 100), 1
                    )
                    self.data["progress"] = self.watched_percentage

                    time_left = int(self.total_time) - int(self.current_time)
                    if self.next_dialog and time_left <= self.playing_next_time:
                        xbmc.executebuiltin(
                            action_url_run(name="run_next_dialog", item_info=self.data)
                        )
                        self.next_dialog = False

                except Exception as e:
                    kodilog(f"Error in monitor: {e}")
                    sleep(250)

            if (
                is_trakt_auth()
                and get_setting("trakt_scrobbling_enabled")
                and self.data.get("ids")
            ):
                TraktAPI().scrobble.trakt_stop_scrobble(self.data)
                
            close_busy_dialog()

        except Exception as e:
            kodilog(f"Monitor failed: {e}")
            self.cancel_all_playback = True
            self.kill_dialog()

        finally:
            self.cancel_playback()
            self.clear_playback_properties()

    def build_playlist(self):
        if self.data.get("mode") != "tv":
            return

        ids = self.data.get("ids")
        if not ids:
            return

        tmdb_id = ids.get("tmdb_id")
        if not tmdb_id:
            return

        details = tmdb_get("tv_details", tmdb_id)
        tv_data = self.data.get("tv_data", {})
        season = tv_data.get("season")
        episode = tv_data.get("episode")

        if season is None or episode is None:
            return

        season_details = tmdb_get("season_details", {"id": tmdb_id, "season": season})

        if not season_details or not hasattr(season_details, "episodes"):
            return

        for e in season_details.episodes:
            episode_name = getattr(e, "name", "")
            episode_number = getattr(e, "episode_number", 0)

            if episode_number <= int(episode):
                continue

            label = f"{season}x{episode_number}. {episode_name}"
            next_tv_data = {
                "name": episode_name,
                "episode": episode_number,
                "season": season,
            }

            url = build_url(
                "search",
                mode=self.data["mode"],
                query=getattr(details, "name", ""),
                ids=ids,
                tv_data=next_tv_data,
                rescrape=True,
            )

            list_item = ListItem(label=label)
            list_item.setPath(url)
            list_item.setProperty("IsPlayable", "true")

            self.PLAYLIST.add(url=url, listitem=list_item)

    def kill_dialog(self):
        close_all_dialog()

    def playback_close_dialogs(self):
        sleep(200)
        close_all_dialog()

    def set_constants(self, data):
        self.PLAYLIST.clear()
        self.data = data
        self.url = self.data["url"]
        self.kodi_monitor = xbmc.Monitor()
        self.watched_percentage = self.data.get("progress", 0.0)

    def clear_playback_properties(self):
        clear_property("script.trakt.ids")

    def add_external_trakt_scrolling(self):
        ids = self.data.get("ids", {})
        mode = self.data.get("mode")
        title = self.data.get("title", "")

        if ids:
            trakt_ids = {
                "tmdb": ids.get("tmdb_id"),
                "imdb": ids.get("imdb_id"),
                "slug": TraktLists().make_trakt_slug(title),
            }
            if mode == "tv":
                trakt_ids["tvdb"] = ids.get("tvdb_id")
            set_property("script.trakt.ids", json_dumps(trakt_ids))

    def mark_watched(self, data):
        set_watched_file(data)

    def cancel_playback(self):
        self.PLAYLIST.clear()
        close_busy_dialog()
        close_all_dialog()
        setResolvedUrl(ADDON_HANDLE, False, ListItem(offscreen=True))

    def run_error(self):
        self.playback_successful = False
        self.clear_playback_properties()
        self.cancel_playback()
        notification("Playback Failed", time=3500)
