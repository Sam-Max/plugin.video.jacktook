from typing import List, Optional, Dict
from lib.domain.torrent import TorrentStream
from lib.gui.filter_type_window import FilterTypeWindow
from lib.gui.filter_items_window import FilterWindow
from lib.gui.base_window import BaseWindow
from lib.gui.resolver_window import ResolverWindow
from lib.gui.resume_window import ResumeDialog
from lib.utils.debrid.debrid_utils import get_source_status
from lib.utils.kodi.utils import (
    action_url_run,
    bytes_to_human_readable,
    ADDON_PATH,
    get_setting,
    kodilog,
    notification,
    translatePath,
    translation,
)
from lib.utils.general.utils import (
    IndexerType,
    extract_publish_date,
    get_colored_languages,
    get_random_color,
)

import xbmcgui
import xbmc


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
        self.list_sources: List[TorrentStream] = []
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
        self.populate_qualities_header()
        self.populate_sources_list()
        self.set_default_focus(self.display_list, 1000, control_list_reset=True)
        super().onInit()

    def populate_qualities_header(self):
        from collections import Counter

        fixed_qualities = [
            ("[B][COLOR yellow]4k[/COLOR][/B]", "4k"),
            ("[B][COLOR blue]1080p[/COLOR][/B]", "1080p"),
            ("[B][COLOR orange]720p[/COLOR][/B]", "720p"),
            ("[B][COLOR yellow]N/A[/COLOR][/B]", "N/A"),
        ]

        qualities = [s.quality for s in self.sources if s.quality]
        counts = Counter(qualities)
        qualities_list = self.getControl(1300)
        qualities_list.reset()

        # Set fixed width for 4 items
        self.setProperty("quality_item_width", str(int(800 / 4)))

        for display, key in fixed_qualities:
            count = counts.get(display, 0)
            label = f"{display} ({count})"
            list_item = xbmcgui.ListItem(label)
            list_item.setProperty("quality", key)
            qualities_list.addItem(list_item)

    def doModal(self) -> Optional[Dict]:
        super().doModal()

    def handle_action(self, action_id: int, control_id: Optional[int] = None) -> None:
        self.position = self.display_list.getSelectedPosition()
        selected_source = self.list_sources[self.position]

        if action_id == 1 and control_id == 1000:
            filter_type_popup = FilterTypeWindow("filter_type.xml", ADDON_PATH)
            filter_type_popup.doModal()
            selected_type = filter_type_popup.selected_type
            del filter_type_popup

            def get_unique(attr):
                return sorted(
                    set(getattr(s, attr) for s in self.sources if getattr(s, attr))
                )

            filter_map = {
                "quality": {
                    "items": lambda: get_unique("quality"),
                    "filter": lambda val: [s for s in self.sources if s.quality == val],
                },
                "provider": {
                    "items": lambda: get_unique("provider"),
                    "filter": lambda val: [
                        s for s in self.sources if s.provider == val
                    ],
                },
                "type": {
                    "items": lambda: get_unique("type"),
                    "filter": lambda val: [s for s in self.sources if s.type == val],
                },
                "indexer": {
                    "items": lambda: get_unique("indexer"),
                    "filter": lambda val: [s for s in self.sources if s.indexer == val],
                },
                "language": {
                    "items": self._get_all_languages,
                    "filter": lambda val: [
                        s
                        for s in self.sources
                        if val in getattr(s, "languages", [])
                        or val in getattr(s, "fullLanguages", [])
                    ],
                },
            }

            if selected_type in filter_map:
                items = filter_map[selected_type]["items"]()
                if selected_type == "language" and not items:
                    notification("No languages found")
                    return
                popup = FilterWindow("filter_items.xml", ADDON_PATH, filter=items)
                popup.doModal()
                selected_filter = popup.selected_filter
                del popup
                if selected_filter is not None:
                    self.filtered_sources = filter_map[selected_type]["filter"](
                        selected_filter
                    )
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
            if selected_source.type == "Torrent":
                response = xbmcgui.Dialog().contextmenu(
                    ["Download to Debrid", translation(90083)]
                )
                if response == 0:
                    self._download_to_debrid()
                elif response == 1:
                    self._download_file(selected_source)
            elif selected_source.type == "Direct":
                response = xbmcgui.Dialog().contextmenu([translation(90083)])
                if response == 0:
                    self._download_file(selected_source)
            else:
                response = xbmcgui.Dialog().contextmenu(
                    [translation(90084), translation(90083), translation(90082)]
                )
                if response == 0:
                    self._resolve_item(selected_source, pack_select=True)
                elif response == 1:
                    self._download_file(selected_source)
                elif response == 2:
                    self._resolve_item(selected_source, is_subtitle_download=True)

        elif control_id == 1300:
            quality_list = self.getControl(1300)
            selected_item = quality_list.getSelectedItem()
            if selected_item:
                selected_quality = selected_item.getProperty("quality")
                self.filtered_sources = [
                    s for s in self.sources if selected_quality in s.quality
                ]
                self.filter_applied = True
                self.populate_sources_list()

        elif action_id == 7 and control_id == 1000:  # Select action
            control_list = self.getControl(control_id)
            self.set_cached_focus(control_id, control_list.getSelectedPosition())
            self._resolve_item(selected_source, pack_select=False)

    def populate_sources_list(self) -> None:
        self.display_list.reset()
        self.list_sources = (
            self.filtered_sources
            if self.filter_applied and self.filtered_sources is not None
            else self.sources
        )
        for source in self.list_sources:
            menu_item = xbmcgui.ListItem(label=source.title)
            menu_item.setProperty("title", source.title)
            if source.type in (IndexerType.TORRENT, IndexerType.STREMIO_DEBRID):
                provider_name = source.type
            else:
                provider_name = source.debridType
            menu_item.setProperty("type", get_random_color(provider_name))
            menu_item.setProperty("indexer", get_random_color(source.indexer))
            menu_item.setProperty("guid", source.guid)
            menu_item.setProperty("infoHash", source.infoHash)
            menu_item.setProperty("size", bytes_to_human_readable(int(source.size)))
            menu_item.setProperty("seeders", str(source.seeders))
            menu_item.setProperty(
                "fullLanguages", get_colored_languages(source.fullLanguages)
            )
            menu_item.setProperty("provider", get_random_color(source.provider))
            menu_item.setProperty(
                "publishDate", extract_publish_date(source.publishDate)
            )
            menu_item.setProperty("peers", str(source.peers))
            menu_item.setProperty("quality", source.quality)
            menu_item.setProperty("status", get_source_status(source))
            menu_item.setProperty("isPack", str(source.isPack))

            self.display_list.addItem(menu_item)

    def _download_to_debrid(self) -> None:
        pass

    def _download_file(self, selected_source) -> None:
        self.playback_info = self._ensure_playback_info(selected_source)
        if self.playback_info:
            self.playback_info.update(self.item_information)
        else:
            notification("Failed to resolve playback source")
            return

        download_dir = get_setting("download_dir")
        try:
            xbmc.executebuiltin(
                action_url_run(
                    "handle_download_file",
                    file_name=self.playback_info["title"],
                    url=self.playback_info["url"],
                    destination=translatePath(download_dir),
                )
            )
        except Exception as e:
            kodilog(f"Failed to start download: {str(e)}")
            xbmcgui.Dialog().notification(
                "Download", f"Failed to start download: {str(e)}"
            )

    def _resolve_item(
        self, selected_source, pack_select: bool = False, is_subtitle_download=False
    ) -> None:
        self.setProperty("resolving", "true")
        resolver_window = ResolverWindow(
            "resolver.xml",
            ADDON_PATH,
            source=selected_source,
            previous_window=self,
            item_information=self.item_information,
            is_subtitle_download=is_subtitle_download,
        )
        resolver_window.doModal(pack_select)
        del resolver_window

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

    def _get_all_languages(self):
        all_languages = set()
        for s in self.sources:
            all_languages.update(getattr(s, "languages", []))
            all_languages.update(getattr(s, "fullLanguages", []))
        return sorted(all_languages)
