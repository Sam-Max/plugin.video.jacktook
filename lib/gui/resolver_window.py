from lib.api.jacktook.kodi import kodilog
from lib.gui.base_window import BaseWindow
from lib.gui.source_pack_select import SourcePackSelect
from lib.play import get_playback_info
from lib.utils.debrid_utils import get_pack_info
from lib.utils.kodi_utils import ADDON_PATH
from lib.utils.utils import Indexer, IndexerType
from lib.utils.resolve_to_magnet import resolve_to_magnet


class ResolverWindow(BaseWindow):
    def __init__(
        self,
        xml_file,
        location=None,
        source=None,
        item_information=None,
        previous_window=None,
        close_callback=None,
    ):
        super().__init__(xml_file, location, item_information=item_information)
        self.stream_data = None
        self.progress = 1
        self.resolver = None
        self.source = source
        self.pack_select = False
        self.item_information = item_information
        self.close_callback = close_callback
        self.playback_info = None
        self.pack_data = None
        self.previous_window = previous_window
        self.setProperty("enable_busy_spinner", "false")

    def doModal(
        self,
        pack_select=False,
    ):
        self.pack_select = pack_select

        if not self.source:
            return

        self._update_window_properties(self.source)
        super().doModal()

    def onInit(self):
        super().onInit()
        self.resolve_source()

    def resolve_source(self):
        type = self.source["type"]
        if type == IndexerType.TORRENT:
            guid = self.source.get("guid")
            magnet = self.source.get("magnet")
            indexer = self.source.get("indexer")
            url = self.source.get("magnetUrl", "") or self.source.get("downloadUrl", "")

            if magnet:
                pass
            elif guid and guid.startswith("magnet:?"):
                magnet = guid
            elif indexer == Indexer.BURST:
                url, magnet = guid, ""
            else:
                magnet = ""

            if url.startswith("magnet:?") and not magnet:
                magnet, url = url, ""

            if not magnet:
                magnet = resolve_to_magnet(url) or ""

            is_torrent = True
        elif type == IndexerType.DIRECT:
            url = self.source.get("downloadUrl")
            magnet = ""
            is_torrent = False
        elif type == IndexerType.STREMIO_DEBRID:
            url = self.source.get("url")
            magnet = ""
            is_torrent = False
        else:
            url = ""
            magnet = ""
            is_torrent = False

        if self.source.get("isPack") or self.pack_select:
            self.resolve_pack()
        else:
            self.resolve_single_source(url, magnet, is_torrent)

        self.close()
        return self.playback_info

    def resolve_single_source(self, url, magnet, is_torrent):
        self.playback_info = get_playback_info(
            data={
                "title": self.source["title"],
                "type": self.source["type"],
                "indexer": self.source["indexer"],
                "url": url,
                "magnet": magnet,
                "info_hash": self.source.get("info_hash", ""),
                "is_torrent": is_torrent,
                "is_pack": self.pack_select,
                "mode": self.item_information["mode"],
                "ids": self.item_information["ids"],
                "tv_data": self.item_information["tv_data"],
            }
        )

    def resolve_pack(self):
        self.pack_data = get_pack_info(
            type=self.source.get("type"),
            info_hash=self.source.get("info_hash"),
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

    def _update_window_properties(self, source):
        self.setProperty("enable_busy_spinner", "true")
