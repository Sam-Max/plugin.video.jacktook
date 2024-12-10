# -*- coding: utf-8 -*-
from threading import Thread
from lib.api.jacktook.kodi import kodilog
from lib.utils.kodi_utils import (
    clear_property,
    close_all_dialog,
    hide_busy_dialog,
    notification,
)
from lib.utils.utils import set_media_infotag, set_windows_property
from xbmc import Monitor, getCondVisibility as get_visibility
from lib.utils.kodi_utils import sleep
import xbmc
from xbmcgui import ListItem

total_time_errors = ("0.0", "", 0.0, None)
set_resume, set_watched = 5, 90
video_fullscreen_check = "Window.IsActive(fullscreenvideo)"


class TestPlayer(xbmc.Player):
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

    def run(self, url=None, data=None):
        hide_busy_dialog()
        self.clear_playback_properties()

        if not url:
            kodilog(f"URL missing: {url}")
            return self.run_error()
        try:
            return self.play_video(url, self.make_listing(data))
        except Exception as e:
            kodilog(f"Error in run: {e}")
            return self.run_error()

    def make_listing(self, metadata):
        url = metadata.get("url")
        title = metadata.get("title")
        ids = metadata.get("ids")
        tv_data = metadata.get("tv_data", {})
        mode = metadata.get("mode", "")

        list_item = ListItem(label=title)
        list_item.setPath(url)
        list_item.setContentLookup(False)
        list_item.setLabel(title)

        if self.playback_percent > 0.0:
            list_item.setProperty("StartPercent", str(self.playback_percent))

        if tv_data:
            ep_name, episode, season = tv_data.split("(^)")
        else:
            ep_name = episode = season = ""

        set_media_infotag(
            list_item,
            mode,
            title,
            season_number=season,
            episode=episode,
            ep_name=ep_name,
            ids=ids,
        )

        set_windows_property(mode, ids)
        return list_item

    def play_video(self, url, list_item):
        self.set_constants(url)
        hide_busy_dialog()

        try:
            self.play(self.url, list_item)
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
                # execute_builtin("SendClick(okdialog, 11)")
                self.playback_successful = False
            elif self.isPlayingVideo():
                kodilog("isPlayingVideo")
                try:
                    if self.getTotalTime() not in total_time_errors and get_visibility(
                        video_fullscreen_check
                    ):
                        self.playback_successful = True
                except Exception as e:
                    kodilog(f"Error in check_playback_start: {e}")

            resolve_percent = round(resolve_percent + 26.0 / 100, 1)
            kodilog(f"resolve_percent: {resolve_percent}")
            sleep(50)

    def playback_close_dialogs(self):
        sleep(200)
        close_all_dialog()

    def monitor(self):
        ensure_dialog_dead = False
        total_check_time = 0

        try:
            while total_check_time <= 30 and not get_visibility(video_fullscreen_check):
                sleep(100)
                total_check_time += 0.10

            hide_busy_dialog()
            sleep(1000)

            while self.isPlayingVideo():
                try:
                    self.total_time, self.curr_time = (
                        self.getTotalTime(),
                        self.getTime(),
                    )

                    if not ensure_dialog_dead:
                        ensure_dialog_dead = True
                        self.playback_close_dialogs()

                    sleep(1000)

                    self.current_point = round(
                        float(self.curr_time / self.total_time * 100), 1
                    )

                    if self.current_point >= set_watched:
                        if not self.media_marked:
                            self.media_watched_marker()

                except Exception as e:
                    kodilog(f"Error in monitor: {e}")
                    sleep(250)

            hide_busy_dialog()

            if not self.media_marked:
                self.media_watched_marker()

        except Exception as e:
            kodilog(f"Monitor failed: {e}")
            self.cancel_all_playback = True
            self.kill_dialog()

        finally:
            self.clear_playback_properties()
            

    def media_watched_marker(self):
        self.media_marked = True
        try:
            if self.current_point >= set_resume:
                self.playback_percent = self.current_point
                self.set_bookmark()
        except Exception as e:
            kodilog(f"Error in media_watched_marker: {e}")

    def kill_dialog(self):
        close_all_dialog()

    def set_constants(self, url):
        self.url = url
        self.kodi_monitor = Monitor()
        self.playback_percent = self.get_bookmark()
        self.playing_filename = ""
        self.media_marked = False
        self.playback_successful = None
        self.cancel_all_playback = False

    def set_bookmark(self):
        Thread(target=self.db.set_bookmark, args=(self.url, self.playback_percent)).start()

    def get_bookmark(self):
        return self.db.get_bookmark(self.url)

    def clear_playback_properties(self):
        clear_property("script.trakt.ids")

    def run_error(self):
        self.playback_successful = False
        self.clear_playback_properties()
        notification(message="Playback Failed", time=3500)
        return False
