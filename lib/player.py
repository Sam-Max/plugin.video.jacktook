from threading import Thread
from lib.utils.kodi_utils import hide_busy_dialog, notification, sleep
from xbmc import Player
import xbmcgui

set_resume = 5


class JacktookPlayer(Player):
    def __init__(self, db):
        Player.__init__(self)
        self.url = None
        self.curr_time = 0.0
        self.resume_time = 0.0
        self.is_playing = False
        self.db = db

    def run(self, list_item):
        hide_busy_dialog()
        if self.url is None:
            self.run_error()
        try:
            if self.resume_time > 0.0:
                choice = xbmcgui.Dialog().yesno(
                    "Resume Playback",
                    "Do you want to resume playback?",
                    yeslabel="Resume",
                    nolabel="From the beginning",
                )
                if choice:
                    list_item.setProperty("StartPercent", str(self.resume_time))
                else:
                    list_item.setProperty("StartPercent", str(0.0))
            self.play_video(list_item)
        except Exception:
            self.stop()
            return self.run_error()

    # def onPlayBackStarted(self):
    #     if self.bookmark > 0.0:
    #         self.seekTime(self.bookmark)

    def onPlayBackStopped(self):
        self.is_playing = False

    def play_video(self, list_item):
        self.is_playing = True 
        self.play(self.url, list_item)
        # if self.resume_time > 0.0:
        #     self.seekTime(self.resume_time)
        Thread(target=self.monitor_playback).start()

    def monitor_playback(self):
        while self.is_playing:
            try:
                self.total_time = self.getTotalTime()
                self.curr_time = self.getTime()
                self.current_point = round(
                    float(self.curr_time / self.total_time * 100), 1
                )
                if self.current_point >= set_resume:
                    self.set_bookmark()
            except:
                sleep(500)
                continue
            sleep(500)
        hide_busy_dialog()
        # if self.current_point >= set_resume:
        #     self.set_bookmark()

    def set_constants(self, url):
        self.url = url
        self.resume_time = self.get_bookmark()
        # if self.resume_time > 0.0:
        #     list_item.setProperty("StartPercent", str(self.resume_time))

    def run_error(self):
        self.is_playing = False
        notification("Playback Failed")

    def set_bookmark(self):
        rounded_time = round(float(self.curr_time / self.total_time * 100), 1)
        self.db.set_bookmark(self.url, rounded_time)

    def get_bookmark(self):
        return self.db.get_bookmark(self.url)
