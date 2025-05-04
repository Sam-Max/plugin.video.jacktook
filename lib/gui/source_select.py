import re
from typing import List, Optional, Dict
from lib.api.jacktook.kodi import kodilog
from lib.domain.torrent import TorrentStream
from lib.gui.filter_type_window import FilterTypeWindow
from lib.gui.filter_items_window import FilterWindow
from lib.play import resolve_playback_source
import xbmcgui
import xbmc
from lib.gui.base_window import BaseWindow
from lib.gui.resolver_window import ResolverWindow
from lib.gui.resume_window import ResumeDialog
from lib.utils.kodi_utils import ADDON_PATH, get_setting, translatePath
from lib.utils.debrid_utils import get_debrid_status
from lib.utils.kodi_utils import bytes_to_human_readable
from lib.utils.utils import (
    extract_publish_date,
    get_colored_languages,
    get_random_color,
)
from lib.utils.kodi_utils import action_url_run


class SourceSelect(BaseWindow):
    def __init__(
        self,
        xml_file: str,
        location: str,
        item_information: Optional[Dict] = None,
        sources: Optional[List[TorrentStream]] = None,
        uncached: Optional[List[TorrentStream]] = None,
    ):
        super().__init__(xml_file, location, item_information=item_information)
        self.uncached_sources: List[TorrentStream] = uncached or []
        self.position: int = -1
        self.sources: List[TorrentStream] = sources or []
        self.item_information: Dict = item_information or {}
        self.playback_info: Optional[Dict] = None
        self.resume: Optional[bool] = None
        self.CACHE_KEY: str = str(self.item_information.get("tv_data", "")) or str(
            self.item_information.get("ids", "")
        )
        self.setProperty("instant_close", "false")
        self.setProperty("resolving", "false")
        self.filtered_sources: Optional[List[TorrentStream]] = None
        self.filter_applied: bool = False

    def onInit(self) -> None:
        self.display_list: xbmcgui.ControlList = self.getControlList(1000)
        self.populate_sources_list()

        self.set_default_focus(self.display_list, 1000, control_list_reset=True)
        super().onInit()

    def doModal(self) -> Optional[Dict]:
        super().doModal()
        return self.playback_info

    def populate_sources_list(self) -> None:
        self.display_list.reset()
        sources = (
            self.filtered_sources
            if self.filter_applied and self.filtered_sources is not None
            else self.sources
        )
        for source in sources:
            menu_item = xbmcgui.ListItem(label=source.title)

            menu_item.setProperty("title", source.title)
            menu_item.setProperty("type", get_random_color(source.type))
            menu_item.setProperty("indexer", get_random_color(source.indexer))
            menu_item.setProperty("guid", source.guid)
            menu_item.setProperty("infoHash", source.infoHash)
            menu_item.setProperty("size", bytes_to_human_readable(int(source.size)))
            menu_item.setProperty("seeders", str(source.seeders))
            menu_item.setProperty("languages", ", ".join(source.languages))
            menu_item.setProperty(
                "fullLanguages", get_colored_languages(source.fullLanguages)
            )
            menu_item.setProperty("provider", get_random_color(source.provider))
            menu_item.setProperty(
                "publishDate", extract_publish_date(source.publishDate)
            )
            menu_item.setProperty("peers", str(source.peers))
            menu_item.setProperty("quality", source.quality)
            menu_item.setProperty("status", get_debrid_status(source))
            menu_item.setProperty("isPack", str(source.isPack))

            self.display_list.addItem(menu_item)

    def handle_action(self, action_id: int, control_id: Optional[int] = None) -> None:
        self.position = self.display_list.getSelectedPosition()

        # Show filter type popup on right arrow
        if action_id == 1 and control_id == 1000:
            filter_type_popup = FilterTypeWindow("filter_type.xml", ADDON_PATH)
            filter_type_popup.doModal()
            selected_type = filter_type_popup.selected_type
            del filter_type_popup

            if selected_type == "quality":
                qualities = sorted(set(s.quality for s in self.sources if s.quality))
                popup = FilterWindow("filter_items.xml", ADDON_PATH, filter=qualities)
                popup.doModal()
                selected = popup.selected_filter
                del popup
                if selected is not None:
                    self.filtered_sources = [
                        s for s in self.sources if s.quality == selected
                    ]
                    self.filter_applied = True
                else:
                    self.filtered_sources = None
                    self.filter_applied = False

            elif selected_type == "provider":
                providers = sorted(set(s.provider for s in self.sources if s.provider))
                popup = FilterWindow("filter_items.xml", ADDON_PATH, filter=providers)
                popup.doModal()
                selected = popup.selected_filter
                del popup
                if selected is not None:
                    self.filtered_sources = [
                        s for s in self.sources if s.provider == selected
                    ]
                    self.filter_applied = True
                else:
                    self.filtered_sources = None
                    self.filter_applied = False
            else:
                self.filtered_sources = None
                self.filter_applied = False

            self.populate_sources_list()
            self.set_default_focus(self.display_list, 1000, control_list_reset=True)

        elif action_id == 117:  # Context menu action
            selected_source = self.sources[self.position]
            if selected_source.type == "Torrent":
                response = xbmcgui.Dialog().contextmenu(
                    ["Download to Debrid", "Download file"]
                )
                if response == 0:
                    self._download_to_debrid()
                elif response == 1:
                    self._download_file()
            elif selected_source.type == "Direct":
                response = xbmcgui.Dialog().contextmenu(["Download file"])
                if response == 0:
                    self._download_file()
            else:
                response = xbmcgui.Dialog().contextmenu(
                    ["Browse into", "Download file"]
                )
                if response == 0:
                    self._resolve_item(pack_select=True)
                elif response == 1:
                    self._download_file()

        elif action_id == 7 and control_id == 1000:  # Select action
            control_list = self.getControl(control_id)
            self.set_cached_focus(control_id, control_list.getSelectedPosition())
            self._resolve_item(pack_select=False)

    def _download_to_debrid(self) -> None:
        pass

    def _download_file(self) -> None:
        selected_source = self.sources[self.position]

        url, magnet, is_torrent = self.get_source_details(source=selected_source)
        source_data = self.prepare_source_data(
            source=selected_source,
            url=url,
            magnet=magnet,
            is_torrent=is_torrent,
        )

        playback_info = resolve_playback_source(source_data)
        if not playback_info or "url" not in playback_info:
            xbmcgui.Dialog().notification(
                "Download", "Failed to resolve playback source."
            )
            return

        download_dir = get_setting("download_dir")
        try:
            xbmc.executebuiltin(
                action_url_run(
                    "download_file",
                    file_name=playback_info["title"],
                    url=playback_info["url"],
                    title=selected_source.title,
                    destination=translatePath(download_dir),
                )
            )
        except Exception as e:
            kodilog(f"Failed to start download: {str(e)}")
            xbmcgui.Dialog().notification(
                "Download", f"Failed to start download: {str(e)}"
            )

    def _resolve_item(self, pack_select: bool = False) -> None:
        self.setProperty("resolving", "true")

        selected_source = self.sources[self.position]

        resolver_window = ResolverWindow(
            "resolver.xml",
            ADDON_PATH,
            source=selected_source,
            previous_window=self,
            item_information=self.item_information,
        )
        resolver_window.doModal(pack_select)
        self.playback_info = resolver_window.playback_info

        del resolver_window
        self.setProperty("instant_close", "true")
        self.close()

    def show_resume_dialog(self, playback_percent: float) -> Optional[bool]:
        try:
            resume_window = ResumeDialog(
                "resume_dialog.xml",
                ADDON_PATH,
                resume_percent=playback_percent,
            )
            resume_window.doModal()
            return resume_window.resume
        finally:
            del resume_window
