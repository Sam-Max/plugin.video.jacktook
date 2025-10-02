from typing import Optional, Dict, Any
from lib.gui.source_pack_window import SourcePackWindow
from lib.utils.general.utils import DebridType
from lib.domain.torrent import TorrentStream
from lib.utils.player.utils import resolve_playback_url


class SourcePackSelect(SourcePackWindow):
    def __init__(
        self,
        xml_file: str,
        location: str,
        source: Optional[TorrentStream] = None,
        pack_info: Optional[Dict[str, Any]] = None,
        item_information: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            xml_file, location, pack_info=pack_info, item_information=item_information
        )
        self.source: Optional[TorrentStream] = source
        self.pack_info: Optional[Dict[str, Any]] = pack_info
        self.position: int = -1
        self.playback_info: Optional[Dict[str, Any]] = None
        self.setProperty("instant_close", "false")
        self.setProperty("resolving", "false")

    def doModal(self) -> Optional[Dict[str, Any]]:
        super().doModal()
        return self.playback_info

    def handle_action(self, action_id: int, control_id: Optional[int] = None) -> None:
        self.position = self.display_list.getSelectedPosition()
        if action_id == 7:
            if control_id == 1000:
                self._resolve_item()

    def _resolve_item(self) -> None:
        self.setProperty("resolving", "true")

        if self.source and self.pack_info:
            common_data = {
                "type": self.source.type,
                "debrid_type": self.source.debridType,
                "is_torrent": False,
                "is_pack": True,
                "mode": self.item_information.get("mode"),
                "ids": self.item_information.get("ids"),
                "tv_data": self.item_information.get("tv_data"),
            }
            if self.source.debridType in [DebridType.RD, DebridType.TB]:
                file_id, name = self.pack_info["files"][self.position]
                self.playback_info = resolve_playback_url(
                    data={
                        **common_data,
                        "title": name,
                        "pack_info": {
                            "file_id": file_id,
                            "torrent_id": self.pack_info["id"],
                        },
                    }
                )
            else:
                url, title = self.pack_info["files"][self.position]
                self.playback_info = resolve_playback_url(
                    data={
                        **common_data,
                        "title": title,
                        "url": url,
                    }
                )

        if not self.playback_info:
            self.setProperty("resolving", "false")
            self.close()
            return

        self.setProperty("instant_close", "true")
        self.close()
