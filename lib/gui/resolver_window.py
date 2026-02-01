from typing import Optional, Dict, Any
from datetime import timedelta

from lib.clients.subtitle.submanager import SubtitleManager
from lib.db.cached import cache
from lib.gui.base_window import BaseWindow
from lib.gui.source_pack_select import SourcePackSelect
from lib.player import JacktookPLayer
from lib.utils.debrid.debrid_utils import get_pack_info
from lib.utils.kodi.utils import get_setting, kodilog
from lib.utils.kodi.utils import ADDON_PATH, notification, set_property
from lib.domain.torrent import TorrentStream


class ResolverWindow(BaseWindow):
    def __init__(
        self,
        xml_file: str,
        location: str,
        source: TorrentStream,
        item_information: Optional[Dict[str, Any]] = None,
        previous_window: Optional[BaseWindow] = None,
        close_callback: Optional[Any] = None,
        is_subtitle_download: bool = False,
    ) -> None:
        super().__init__(
            xml_file,
            location,
            item_information=item_information,
            previous_window=previous_window,
        )
        self.stream_data: Optional[Any] = None
        self.progress: int = 1
        self.resolver: Optional[Any] = None
        self.source: TorrentStream = source
        self.pack_select: bool = False
        self.is_subtitle_download = is_subtitle_download
        self.item_information: Dict = item_information or {}
        self.close_callback: Optional[Any] = close_callback
        self.playback_info: Optional[Dict[str, Any]] = None
        self.pack_info: Optional[Any] = None
        self.previous_window: BaseWindow = previous_window
        self.setProperty("enable_busy_spinner", "false")
        self.resolved = False

    def doModal(
        self,
        pack_select: bool = False,
    ) -> bool:
        self.pack_select = pack_select

        self._update_window_properties(self.source)
        super().doModal()
        return self.resolved

    def onInit(self) -> None:
        super().onInit()
        self.resolve_source()

    def close_windows(self):
        if self.previous_window:
            self.previous_window.setProperty("instant_close", "true")
            self.previous_window.close()
        self.close()

    def handle_playback_started(self):
        self.resolved = True
        self.close_windows()

    def resolve_source(self) -> Optional[Dict[str, Any]]:
        try:
            if self.source.isPack or self.pack_select:
                self.resolve_pack_source()
            else:
                self.resolve_single_source()

            if self.is_subtitle_download:
                self._download_subtitle()

            if not self.playback_info:
                raise Exception("Failed to resolve source")

            player = JacktookPLayer(
                on_started=self.handle_playback_started,
                on_error=self.handle_playback_started,
            )
            player.run(data=self.playback_info)
        except Exception as e:
            import traceback

            kodilog(f"Error in resolver window: {e}")
            kodilog(traceback.format_exc())
            if self.previous_window:
                self.previous_window.setProperty("instant_close", "true")
                self.previous_window.close()
            self.close()

    def resolve_single_source(self) -> None:
        self.playback_info = self._ensure_playback_info(source=self.source)
        if self.playback_info:
            self.playback_info.update(self.item_information)
            self._cache_playback_info()

    def resolve_pack_source(self) -> None:
        self.pack_info = get_pack_info(
            debrid_type=self.source.debridType,
            info_hash=self.source.infoHash,
        )
        self.window = SourcePackSelect(
            "source_pack_select.xml",
            ADDON_PATH,
            source=self.source,
            pack_info=self.pack_info,
            item_information=self.item_information,
        )
        self.playback_info = self.window.doModal()
        if self.playback_info:
            self.playback_info.update(self.item_information)
            self._cache_playback_info()
        else:
            self.close_windows()

        del self.window

    def _cache_playback_info(self) -> None:
        if get_setting("super_quick_play", False):
            kodilog("Super quick play enabled, caching playback info")
            key = ""
            if "ids" in self.playback_info and "tmdb_id" in self.playback_info["ids"]:
                key = str(self.playback_info["ids"]["tmdb_id"])
                if "season" in self.playback_info.get(
                    "tv_data", {}
                ) and "episode" in self.playback_info.get("tv_data", {}):
                    key += f'_{self.playback_info["tv_data"]["season"]}_{self.playback_info["tv_data"]["episode"]}'

            if key:
                cache.set(key, self.playback_info, timedelta(days=30))
                kodilog("Playback info cached")

    def _download_subtitle(self):
        subtitle_manager = SubtitleManager(self.playback_info, notification)
        subtitles_path = subtitle_manager.fetch_subtitles()
        if not subtitles_path:
            from lib.gui.resolver_window import SourceException

            raise SourceException("Failed to download subtitles for the current source")

        set_property("search_subtitles", "true")
        if self.playback_info:
            self.playback_info.update({"subtitles_path": subtitles_path})

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
