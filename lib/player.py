from json import dumps as json_dumps
from threading import Thread
from lib.api.jacktook.kodi import kodilog
from lib.api.trakt.trakt_api import make_trakt_slug
from lib.utils.kodi_utils import (
    ADDON_HANDLE,
    PLAYLIST,
    action_url_run,
    build_url,
    clear_property,
    close_all_dialog,
    close_busy_dialog,
    execute_builtin,
    get_setting,
    notification,
    set_property,
)
from lib.utils.tmdb_utils import tmdb_get
from lib.utils.utils import (
    make_listing,
)
from xbmc import Monitor, getCondVisibility as get_visibility
from lib.utils.kodi_utils import sleep
import xbmc
from xbmcgui import ListItem
from xbmcplugin import setResolvedUrl


total_time_errors = ("0.0", "", 0.0, None)
set_resume, set_watched = 5, 90
video_fullscreen_check = "Window.IsActive(fullscreenvideo)"


class JacktookPLayer(xbmc.Player):
    def __init__(self, db):
        xbmc.Player.__init__(self)
        self.url = None
        self.db = db
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

        close_busy_dialog()

        try:
            list_item = make_listing(data)
            self.PLAYLIST.add(self.url, list_item)
            if self.data["mode"] == "tv":
                self.build_playlist()
            self.play_video(list_item)
        except Exception as e:
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
            self.run_error()
        finally:
            try:
                del self.kodi_monitor
            except:
                pass

    def check_playback_start(self):
        kodilog("check_playback_start")
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
                kodilog("isPlayingVideo")
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
        kodilog("playback monitor")
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

                    time_left = int(self.total_time) - int(self.current_time)

                    if self.next_dialog and time_left <= self.playing_next_time:
                        xbmc.executebuiltin(
                            action_url_run(name="run_next_dialog", item_info=self.data)
                        )
                        self.next_dialog = False

                    # if self.current_point >= set_watched:
                    #     if not self.media_marked:
                    #         self.media_watched_marker()

                except Exception as e:
                    kodilog(f"Error in monitor: {e}")
                    sleep(250)

            close_busy_dialog()

            # if not self.media_marked:
            #     self.media_watched_marker()

        except Exception as e:
            kodilog(f"Monitor failed: {e}")
            self.cancel_all_playback = True
            self.kill_dialog()

        finally:
            self.cancel_playback()
            self.clear_playback_properties()

    def build_playlist(self):
        if self.data["mode"] == "tv":
            ids = self.data.get("ids")
            if ids:
                tmdb_id, _, _ = [id.strip() for id in ids.split(',')]

                details = tmdb_get("tv_details", tmdb_id)
                name = details.name
                tv_data = self.data["tv_data"]
                _, episode_number, season_number = tv_data.split("(^)")

                season_details = tmdb_get(
                    "season_details", {"id": tmdb_id, "season": season_number}
                )
                for episode in season_details.episodes:
                    episode_name = episode.name
                    _episode_number = episode.episode_number
                    if _episode_number <= int(episode_number):
                        continue
                    label = f"{season_number}x{_episode_number}. {episode_name}"
                    tv_data = f"{episode_name}(^){_episode_number}(^){season_number}"

                    url = build_url(
                        "search",
                        mode=self.data["mode"],
                        query=name,
                        ids=ids,
                        tv_data=tv_data,
                        rescrape=True,
                    )

                    list_item = ListItem(label=label)
                    list_item.setPath(url)
                    list_item.setProperty("IsPlayable", "true")

                    self.PLAYLIST.add(url=url, listitem=list_item)

    def media_watched_marker(self):
        self.media_marked = True
        try:
            if self.watched_percentage >= set_resume:
                self.set_bookmark()
        except Exception as e:
            kodilog(f"Error in media_watched_marker: {e}")

    def set_bookmark(self):
        Thread(
            target=self.db.set_bookmark, args=(self.db_key, self.watched_percentage)
        ).start()

    def get_bookmark(self):
        return self.db.get_bookmark(self.db_key)

    def kill_dialog(self):
        close_all_dialog()

    def playback_close_dialogs(self):
        sleep(200)
        close_all_dialog()

    def set_constants(self, data):
        self.PLAYLIST.clear()
        self.data = data
        self.url = self.data["url"]
        self.db_key = self.data.get("info_hash") or self.url
        self.kodi_monitor = Monitor()
        self.watched_percentage = self.get_bookmark()

    def clear_playback_properties(self):
        clear_property("script.trakt.ids")

    def add_external_trakt_scrolling(self):
        ids = self.data.get("ids")
        mode = self.data.get("mode")

        if ids:
            tmdb_id, tvdb_id, imdb_id = [id.strip() for id in ids.split(',')]
            trakt_ids = {
                "tmdb": tmdb_id,
                "imdb": imdb_id,
                "slug": make_trakt_slug(self.data.get("title")),
            }
            if mode == "tv":
                trakt_ids["tvdb"] = tvdb_id
            set_property("script.trakt.ids", json_dumps(trakt_ids))

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
