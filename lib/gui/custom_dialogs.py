from xbmcgui import WindowXMLDialog, WindowXML
import xbmcgui

from lib.api.jacktook.kodi import kodilog
from lib.gui.resolver_window import ResolverWindow
from lib.utils.kodi_utils import ADDON_PATH
from lib.gui.source_select import SourceSelect


class CustomWindow(WindowXML):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def onInit(self):
        pass


class MyWindow(WindowXML):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.list_control = None

    def onInit(self):
        self.list_control = self.getControl(32503)

    def add_item(self, list_item):
        if self.list_control:
            self.list_control.addItem(list_item)

    def onClick(self, control_id):
        if control_id == 32503:  # List control
            selected_item = self.list_control.getSelectedItem()
            if selected_item:
                xbmcgui.Dialog().notification(
                    "Selected Item",
                    selected_item.getLabel(),
                    xbmcgui.NOTIFICATION_INFO,
                    3000,
                )


class CustomDialog(WindowXMLDialog):
    _heading = 32500
    _text = 32501
    _close_button_id = 32503

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.heading = kwargs.get("heading")
        self.text = kwargs.get("text")

    def onInit(self):
        self.getControl(self._heading).setLabel(self.heading)
        self.getControl(self._text).setLabel(self.text)

    def onClick(self, controlId):
        if controlId == self._close_button_id:
            self.close()


mock_source = {
    "type": "torrent",
    "info": {"HEVC", "DV", "HDR", "HYBRID", "REMUX", "ATMOS", "TRUEHD", "7.1"},
    "quality": "1080p",
    "hash": "hash",
    "size": 1400,
    "provider": "Test Provider",
    "title": "Test.Source.1999.UHD.BDRemux.TrueHD.Atmos.7.1.HYBRID.DoVi.mkv",
    "debrid_provider": "premiumize",
    "seeds": 123,
}

_mock_information = {
    "fanart": "",
    "clearlogo": "https://assets.fanart.tv/fanart/movies/86161/hdmovielogo/mobile-suit-gundam-0083-the-last-blitz-of-zeon-5c2ede0c7530d.png",
    "plot": "Silo is the story of the last ten thousand people on earth, their mile-deep home protecting them from the toxic and deadly world outside. However, no one knows when or why the silo was built and any who try to find out face fatal consequences.",
}


def source_select(item_info, sources):
    kodilog(item_info)
    window = SourceSelect(
        "source_select.xml",
        ADDON_PATH,
        item_information=item_info,
        sources=sources,
        uncached=sources,
    )
    data = window.doModal()
    del window
    return data


def source_select_mock():
    sources = [mock_source for _ in range(10)]

    window = SourceSelect(
        "source_select.xml",
        ADDON_PATH,
        item_information=_mock_information,
        sources=sources,
        uncached=sources,
    )
    window.doModal()
    del window


def resolver_mock():
    window = ResolverWindow(
        "resolver.xml",
        ADDON_PATH,
        source=mock_source,
        item_information=_mock_information,
    )
    window.doModal()
    del window
