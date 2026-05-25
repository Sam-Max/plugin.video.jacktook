import contextlib
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List

import xbmcgui
from xbmcgui import WindowXML, WindowXMLDialog

from lib.domain.torrent import TorrentStream
from lib.gui.custom_progress import CustomProgressDialog
from lib.gui.play_next_window import PlayNext
from lib.gui.resolver_window import ResolverWindow
from lib.gui.resume_window import ResumeDialog
from lib.gui.search_status_window import SearchStatusWindow, SearchTaskManager
from lib.gui.source_select import SourceSelect
from lib.utils.kodi.utils import (
    ADDON_PATH,
    PLAYLIST,
    clear_property,
    kodilog,
    set_property,
    translation,
)


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
            if not self.list_control:
                return
            selected_item = self.list_control.getSelectedItem()
            if selected_item:
                xbmcgui.Dialog().notification(
                    translation(90664),
                    selected_item.getLabel(),
                    xbmcgui.NOTIFICATION_INFO,
                    3000,
                )


class CustomDialog(WindowXMLDialog):
    _heading = 32500
    _text = 32501
    _url = 32502
    _close_button_id = 32503
    _qrcode = 32504
    _call_to_action = 32505

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.heading = kwargs.get("heading")
        self.text = kwargs.get("text")
        self.url = kwargs.get("url")
        self.qrcode_path = kwargs.get("qrcode")
        self.call_to_action = kwargs.get("call_to_action")

    def onInit(self):
        self.getControl(self._heading).setLabel(self.heading)
        self.getControl(self._text).setLabel(self.text)
        self.getControl(self._url).setLabel(self.url)
        self.getControl(self._call_to_action).setLabel(self.call_to_action or "")
        if self.qrcode_path:
            self.getControl(self._qrcode).setImage(self.qrcode_path)
            self.getControl(self._qrcode).setVisible(True)
        else:
            with contextlib.suppress(BaseException):
                self.getControl(self._qrcode).setVisible(False)

    def onClick(self, controlId):
        if controlId == self._close_button_id:
            self.close()


fake_torrent = TorrentStream(
    title="Example Movie 2025",
    type="movie",
    indexer="FakeIndexer",
    guid="1234567890abcdef",
    infoHash="abcdef1234567890abcdef1234567890abcdef12",
    size=2_147_483_648,  # 2 GB
    seeders=150,
    languages=["en", "es"],
    fullLanguages="English, Spanish",
    provider="FakeProvider",
    publishDate="2025-08-11T12:00:00Z",
    peers=200,
    quality="1080p",
    url="magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
    isPack=False,
    isCached=True,
)


_mock_information = {
    "fanart": "https://assets.fanart.tv/fanart/tv/453280/showbackground/secret-level-674c531a09534.jpg",
    "poster": "http://image.tmdb.org/t/p/w780/856MRq23grNxpeVl1PdFgmmLiT0.jpg",
    "clearlogo": "https://assets.fanart.tv/fanart/movies/86161/hdmovielogo/mobile-suit-gundam-0083-the-last-blitz-of-zeon-5c2ede0c7530d.png",
    "plot": "Silo is the story of the last ten thousand people on earth, their mile-deep home protecting them from the toxic and deadly world outside. However, no one knows when or why the silo was built and any who try to find out face fatal consequences.",
}


def source_select(item_info: Dict[str, str], xml_file: str, sources: List[TorrentStream]) -> bool:
    window = SourceSelect(
        xml_file,
        ADDON_PATH,
        item_information=item_info,
        sources=sources,
        uncached=sources,
    )
    resolved = window.doModal()
    del window
    return resolved


def run_next_dialog(params):
    try:
        playlist_size = PLAYLIST.size()
        playlist_pos = PLAYLIST.getposition() if playlist_size > 0 else -1
    except Exception as e:
        kodilog(f"Error accessing playlist in run_next_dialog: {e}")
        return

    window = None
    try:
        item_information = json.loads(params["item_info"])
        if playlist_size > 0 and playlist_pos >= 0 and playlist_pos < playlist_size - 1:
            try:
                next_item = PLAYLIST[playlist_pos + 1]
                next_label = next_item.getLabel()
                if next_label:
                    item_information["next_label"] = next_label
            except Exception as e:
                kodilog(f"Unable to read next playlist item label: {e}")
        else:
            kodilog("No next playlist item label available for PlayNext dialog")

        window = PlayNext(
            "playing_next.xml",
            ADDON_PATH,
            item_information=item_information,
        )
        window.doModal()
    finally:
        action = window.action if window else None
        if window is not None:
            del window

        if action == "next_episode":
            set_property("jacktook_next_dialog_action", "next_episode")
        else:
            clear_property("jacktook_next_dialog_action")


def run_resume_dialog(params):
    resume_window = None
    try:
        resume_window = ResumeDialog(
            "resume_dialog.xml",
            ADDON_PATH,
            resume_percent=params.get("resume"),
        )
        resume_window.doModal()
        return resume_window.resume
    finally:
        if resume_window is not None:
            del resume_window


def run_skip_intro_dialog(params):
    """Show skip intro/recap overlay during playback."""
    window = None
    try:
        segment_data = json.loads(params.get("segment_data", "{}"))
        label = params.get("skip_label", translation(90160))

        from lib.gui.skip_intro_window import SkipIntroWindow

        window = SkipIntroWindow(
            "skip_intro.xml",
            ADDON_PATH,
            segment_data=segment_data,
            label=label,
        )
        window.doModal()
    except Exception as e:
        kodilog(f"Error in run_skip_intro_dialog: {e}")
    finally:
        if window is not None:
            del window


def run_next_mock():
    window = None
    try:
        window = PlayNext(
            "playing_next.xml",
            ADDON_PATH,
            item_information=_mock_information,
        )
        window.doModal()
    finally:
        if window is not None:
            del window


def source_select_mock():
    sources = [fake_torrent for _ in range(10)]
    window = SourceSelect(
        "source_select.xml",
        ADDON_PATH,
        item_information=_mock_information,
        sources=sources,
        uncached=sources,
    )
    window.doModal()
    del window


def download_dialog_mock():
    try:
        progress_dialog = CustomProgressDialog("custom_progress_dialog.xml", ADDON_PATH)
        progress_dialog.doModal()
    finally:
        pass


def resume_dialog_mock():
    window = None
    try:
        window = ResumeDialog(
            "resume_dialog.xml",
            ADDON_PATH,
            resume_percent=25.0,
        )
        window.doModal()
        return window.resume
    finally:
        if window is not None:
            del window


def resolver_mock():
    window = ResolverWindow(
        "resolver.xml",
        ADDON_PATH,
        source=fake_torrent,
        item_information=_mock_information,
    )
    window.doModal()
    del window


def search_status_mock():
    # Create dummy tasks that succeed/fail slowly
    import time

    def dummy_task(sleep_time, fail=False, results=10):
        time.sleep(sleep_time)
        if fail:
            raise Exception("Mock failure")
        return [fake_torrent] * results

    with ThreadPoolExecutor(max_workers=5) as executor:
        manager = SearchTaskManager(executor)
        manager.submit_task("Torrentio", "torrentio", dummy_task, 3, False, 15)
        manager.submit_task("Jackett", "jackett", dummy_task, 5, False, 5)
        manager.submit_task("Stremio", "stremio", dummy_task, 8, False, 20)
        manager.submit_task("Prowlarr", "prowlarr", dummy_task, 4, True, 0)

        window = SearchStatusWindow("search_status.xml", ADDON_PATH, task_manager=manager)
        window.doModal()
        del window
