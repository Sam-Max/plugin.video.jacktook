import abc
from lib.api.jacktook.kodi import kodilog
from lib.gui.base_window import BaseWindow
import xbmc


class PlayWindow(BaseWindow):
    def __init__(self, xml_file, xml_location, item_information=None):
        try:
            super().__init__(xml_file, xml_location, item_information=item_information)
            self.player = xbmc.Player()
            self.playing_file = self.getPlayingFile()
            self.duration = self.getTotalTime() - self.getTime()
            self.closed = False
        except Exception as e:
            kodilog(f"Error PlayWindow: {e}")

    def __del__(self):
        self.player = None
        del self.player

    def getTotalTime(self):
        return self.player.getTotalTime() if self.isPlaying() else 0

    def getTime(self):
        return self.player.getTime() if self.isPlaying() else 0

    def isPlaying(self):
        return self.player.isPlaying()

    def getPlayingFile(self):
        return self.player.getPlayingFile()

    def seekTime(self, seekTime):
        self.player.seekTime(seekTime)

    def pause(self):
        self.player.pause()

    def onInit(self):
        self.background_tasks()
        super().onInit()

    def calculate_percent(self):
        return ((int(self.getTotalTime()) - int(self.getTime())) / float(self.duration)) * 100

    def background_tasks(self):
        try:
            try:
                progress_bar = self.getControlProgress(3014)
            except RuntimeError:
                progress_bar = None

            while (
                int(self.getTotalTime()) - int(self.getTime()) > 2
                and not self.closed
                and self.playing_file == self.getPlayingFile()
            ):
                xbmc.sleep(500)
                if progress_bar is not None:
                    progress_bar.setPercent(self.calculate_percent())

            self.smart_play_action()
        except Exception as e:
            kodilog(f"Error: {e}")

        self.close()

    @abc.abstractmethod
    def smart_play_action(self):
        """
        Perform the default smartplay action at window timeout
        :return:
        """

    def close(self):
        self.closed = True
        super().close()

    def handle_action(self, action, control_id=None):
        if action == 7:
            if control_id == 3001:
                xbmc.executebuiltin('PlayerControl(BigSkipForward)')
                self.close()
            if control_id == 3002:
                self.close()
