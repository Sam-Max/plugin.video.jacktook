from lib.gui.play_window import PlayWindow


from lib.utils.kodi.utils import get_setting


class PlayNext(PlayWindow):
    def __init__(self, xml_file, xml_location, item_information=None):
        super().__init__(xml_file, xml_location, item_information=item_information)
        self.default_action = 2

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
