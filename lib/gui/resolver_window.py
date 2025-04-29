from typing import Optional, Dict, Any
from lib.api.jacktook.kodi import kodilog
from lib.gui.base_window import BaseWindow
from lib.gui.source_pack_select import SourcePackSelect
from lib.play import resolve_playback_source
from lib.utils.debrid_utils import get_pack_info
from lib.utils.kodi_utils import ADDON_PATH
from lib.utils.utils import Indexer, IndexerType
from lib.utils.resolve_to_magnet import resolve_to_magnet
from lib.domain.torrent import TorrentStream


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
        self.item_information: Optional[Dict[str, Any]] = item_information
        self.close_callback: Optional[Any] = close_callback
        self.playback_info: Optional[Dict[str, Any]] = None
        self.pack_data: Optional[Any] = None
        self.previous_window: Optional[BaseWindow] = previous_window
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

    def resolve_source(self) -> Optional[Dict[str, Any]]:
        if self.source.isPack or self.pack_select:
            self.resolve_pack()
        else:
            self.resolve_single_source()

        self.close()
        return self.playback_info

    def resolve_single_source(self) -> None:
        url, magnet, is_torrent = self.get_source_details(source=self.source)
        source_data = self.prepare_source_data(self.source, url, magnet, is_torrent)
        self.playback_info = resolve_playback_source(source_data)

        if self.playback_info and self.playback_info.get("is_pack"):
            self.resolve_pack()

    def resolve_pack(self) -> None:
        self.pack_data = get_pack_info(
            type=self.source.type,
            info_hash=self.source.infoHash,
        )

        self.window = SourcePackSelect(
            "source_select.xml",
            ADDON_PATH,
            source=self.source,
            pack_info=self.pack_data,
            item_information=self.item_information,
        )

        self.playback_info = self.window.doModal()
        del self.window

    def _update_window_properties(self, source: TorrentStream) -> None:
        self.setProperty("enable_busy_spinner", "true")
