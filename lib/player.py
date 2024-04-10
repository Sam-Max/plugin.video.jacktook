from lib.utils.kodi import hide_busy_dialog, notify
from xbmc import Player as xbmc_player


class JacktookPlayer(xbmc_player):
    def __init__(self):
        xbmc_player.__init__(self)

    def run(self, list_item=None):
        hide_busy_dialog()
        if not self.url:
            return self.run_error()
        try:
            return self.play_video(list_item)
        except:
            return self.run_error()

    def play_video(self, list_item):
        self.play(self.url, list_item)

    def set_constants(self, url):
        self.url = url

    def run_error(self):
        notify("Playback Failed")
        return False

