from lib.gui.play_window import PlayWindow


class PlayNext(PlayWindow):
    def __init__(self, xml_file, xml_location, item_information=None):
        super().__init__(xml_file, xml_location, item_information=item_information)
        self.default_action = 2

    def smart_play_action(self):
        if (
            self.default_action == 1
            and self.playing_file == self.getPlayingFile()
            and not self.closed
        ):
            self.pause()
