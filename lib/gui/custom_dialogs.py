from xbmcgui import WindowXMLDialog, WindowXML
import xbmcgui

from lib.api.jacktook.kodi import kodilog
from lib.gui.next_window import PlayNext
from lib.gui.resolver_window import ResolverWindow
from lib.gui.resume_window import ResumeDialog
from lib.utils.kodi_utils import ADDON_PATH, PLAYLIST


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
    _url = 32502
    _close_button_id = 32503

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.heading = kwargs.get("heading")
        self.text = kwargs.get("text")
        self.url = kwargs.get("url")

    def onInit(self):
        self.getControl(self._heading).setLabel(self.heading)
        self.getControl(self._text).setLabel(self.text)
        self.getControl(self._url).setLabel(self.url)

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
    "fanart": "https://assets.fanart.tv/fanart/tv/453280/showbackground/secret-level-674c531a09534.jpg",
    "poster": "http://image.tmdb.org/t/p/w780/856MRq23grNxpeVl1PdFgmmLiT0.jpg",
    "clearlogo": "https://assets.fanart.tv/fanart/movies/86161/hdmovielogo/mobile-suit-gundam-0083-the-last-blitz-of-zeon-5c2ede0c7530d.png",
    "plot": "Silo is the story of the last ten thousand people on earth, their mile-deep home protecting them from the toxic and deadly world outside. However, no one knows when or why the silo was built and any who try to find out face fatal consequences.",
}

def run_next_dialog(params):
    kodilog("run_next_dialog")
    if PLAYLIST.size() > 0 and PLAYLIST.getposition() != (PLAYLIST.size() - 1):
        try:
            window = PlayNext(
                "playing_next.xml",
                ADDON_PATH,
                item_information=eval(params["item_info"]),
            )
            window.doModal()
        finally:
            del window

def run_resume_dialog(params):
    try:
        resume_window = ResumeDialog(
            "resume_dialog.xml",
            ADDON_PATH,
            resume_percent=params.get("resume"),
        )
        resume_window.doModal()
        return resume_window.resume
    finally:
        del resume_window

def run_next_mock():
    try:
        window = PlayNext(
            "playing_next.xml",
            ADDON_PATH,
            item_information=_mock_information,
        )
        window.doModal()
    finally:
        del window


def resume_dialog_mock():
    try:
        window = ResumeDialog(
            "resume_dialog.xml",
            ADDON_PATH,
            resume_percent=25.0,
        )
        window.doModal()
        return window.resume
    finally:
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
