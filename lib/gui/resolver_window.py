from typing import Optional, Dict, Any
from lib.gui.base_window import BaseWindow
from lib.gui.source_pack_select import SourcePackSelect
from lib.player import JacktookPLayer
from lib.utils.debrid.debrid_utils import get_pack_info
from lib.utils.kodi.utils import ADDON_PATH, notification
from lib.domain.torrent import TorrentStream
from lib.utils.player.utils import resolve_playback_source


class ResolverWindow(BaseWindow):
    def __init__(
        self,
        xml_file: str,
        location: Optional[str] = None,
        source: Optional[TorrentStream] = None,
        item_information: Optional[Dict[str, Any]] = None,
        previous_window: Optional[BaseWindow] = None,
        close_callback: Optional[Any] = None,
    ) -> None:
        super().__init__(xml_file, location, item_information=item_information)
        self.stream_data: Optional[Any] = None
        self.progress: int = 1
        self.resolver: Optional[Any] = None
        self.source: Optional[TorrentStream] = source
        self.pack_select: bool = False
        self.item_information: Dict = item_information or {}
        self.close_callback: Optional[Any] = close_callback
        self.playback_info: Optional[Dict[str, Any]] = None
        self.pack_data: Optional[Any] = None
        self.previous_window: BaseWindow = previous_window
        self.setProperty("enable_busy_spinner", "false")

    def doModal(
        self,
        pack_select: bool = False,
    ) -> Optional[Dict[str, Any]]:
        self.pack_select = pack_select

        if not self.source:
            return

        self._update_window_properties(self.source)
        super().doModal()

    def onInit(self) -> None:
        super().onInit()
        self.resolve_source()

    def handle_playback_started(self):
        # Close dialog only when playback has begun
        self.previous_window.setProperty("instant_close", "true")
        self.previous_window.close()
        self.close()

    def resolve_source(self) -> Optional[Dict[str, Any]]:
        if self.source.isPack or self.pack_select:
            self.resolve_pack()
        else:
            self.resolve_single_source()

        player = JacktookPLayer(on_started=self.handle_playback_started)
        player.run(data=self.playback_info)
        del player

    def resolve_single_source(self) -> None:
        url, magnet, is_torrent = self.get_source_details(source=self.source)
        source_data = self.prepare_source_data(self.source, url, magnet, is_torrent)
        self.playback_info = resolve_playback_source(source_data)
        if self.playback_info:
            self.playback_info.update(self.item_information)
            if self.playback_info.get("is_pack"):
                self.resolve_pack()

    def resolve_pack(self) -> None:
        self.pack_data = get_pack_info(
            debrid_type=self.source.debridType,
            info_hash=self.source.infoHash,
        )

        self.window = SourcePackSelect(
            "source_pack_select.xml",
            ADDON_PATH,
            source=self.source,
            pack_info=self.pack_data,
            item_information=self.item_information,
        )

        self.playback_info = self.window.doModal()

        if self.playback_info is None:
            self.previous_window.setProperty("instant_close", "true")
            self.previous_window.close()
            self.close()
            del self.window
            raise SourceException("No files on the current source")

        del self.window

    def _update_window_properties(self, source: TorrentStream) -> None:
        self.setProperty("enable_busy_spinner", "true")


class SourceException(Exception):
    def __init__(
        self, message: str, status_code: Optional[int] = None, error_content: Any = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_content = error_content
        details = f"{self.message}"
        if self.status_code is not None:
            details += f" (Status code: {self.status_code})"
        if self.error_content is not None:
            details += f"\nError content: {self.error_content}"
        super().__init__(details)
        notification(details)
