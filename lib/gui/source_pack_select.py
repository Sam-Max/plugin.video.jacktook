from lib.gui.source_pack_window import SourcePackWindow
from lib.play import get_playback_info
from lib.utils.utils import Debrids


class SourcePackSelect(SourcePackWindow):
    def __init__(
        self, xml_file, location, source=None, pack_info=None, item_information=None
    ):
        super().__init__(
            xml_file, location, pack_info=pack_info, item_information=item_information
        )
        self.source = source
        self.pack_info = pack_info
        self.position = -1
        self.playback_info = None
        self.setProperty("instant_close", "false")
        self.setProperty("resolving", "false")

    def doModal(self):
        super().doModal()
        return self.playback_info

    def handle_action(self, action_id, control_id=None):
        self.position = self.display_list.getSelectedPosition()
        if action_id == 7:
            if control_id == 1000:
                self._resolve_item()

    def _resolve_item(self):
        self.setProperty("resolving", "true")

        if self.source["type"] in [Debrids.RD, Debrids.TB]:
            torrent_id = self.pack_info["id"]
            file_id, name = self.pack_info["files"][self.position]
            self.playback_info = get_playback_info(
                data={
                    "title": name,
                    "type": self.source["type"],
                    "is_torrent": False,
                    "is_pack": True,
                    "pack_info": {
                        "file_id": file_id,
                        "torrent_id": torrent_id,
                    },
                    "mode": self.item_information["mode"],
                    "ids": self.item_information["ids"],
                    "tv_data": self.item_information["tv_data"],
                }
            )
        else:
            url, title = self.pack_info
            self.source["url"] = url
            self.source["title"] = title
            self.playback_info = self.source

        if not self.playback_info:
            self.setProperty("resolving", "false")
            self.close()

        self.setProperty("instant_close", "true")
        self.close()

