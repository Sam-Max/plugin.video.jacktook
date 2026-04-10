from typing import List, Optional, Dict
from lib.domain.torrent import TorrentStream
from lib.gui.filter_type_window import FilterTypeWindow
from lib.gui.filter_items_window import FilterWindow
from lib.gui.base_window import BaseWindow
from lib.gui.resolver_window import ResolverWindow
from lib.gui.resume_window import ResumeDialog
from lib.utils.debrid.debrid_utils import (
    add_source_to_debrid,
    get_torrent_data_from_uri,
    get_source_status,
)
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
    get_info_hash_from_magnet,
    get_colored_languages,
    get_provider_color,
    get_random_color,
)
from lib.utils.parsers.title_parser import parse_title_info
from lib.utils.torrent.torrserver_utils import add_source_to_torrserver

import xbmcgui
import xbmc


THEMES = {
    "0": {"card_bg": "FF362e33", "card_focus": "992A3E5C", "card_accent": "FF00559D"},
    "1": {"card_bg": "FF000000", "card_focus": "FF1A1A1A", "card_accent": "FF333333"},
    "2": {"card_bg": "FF1A0B2E", "card_focus": "994D004D", "card_accent": "FF00F3FF"},
    "3": {"card_bg": "FF1B261B", "card_focus": "992D402D", "card_accent": "FF7CFC00"},
    "4": {"card_bg": "FF141414", "card_focus": "992B2510", "card_accent": "FFD4AF37"},
}


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
        self.resolved = False

    def onInit(self) -> None:
        theme_index = get_setting("source_select_theme", "0")
        theme = THEMES.get(str(theme_index), THEMES["0"])
        self.setProperty("style.card_bg", theme["card_bg"])
        self.setProperty("style.card_focus", theme["card_focus"])
        self.setProperty("style.card_accent", theme["card_accent"])

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

    def doModal(self) -> bool:
        super().doModal()
        return self.resolved

    def handle_action(self, action_id: int, control_id: Optional[int] = None) -> None:
        if action_id == 1 and control_id == 1000:
            self._handle_filter_action()
        elif action_id == 117:  # Context menu action
            self._handle_context_menu_action()
        elif control_id == 1300:
            self._handle_quality_select_action()
        elif action_id == 7 and control_id == 1000:  # Select action
            self._handle_select_action(control_id)

    def _handle_filter_action(self):
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
                "filter": lambda val: [s for s in self.sources if s.provider == val],
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

        one_click_filters = {
            "only_torrents": lambda: [s for s in self.sources if s.type == "Torrent"],
            "only_debrid": lambda: [s for s in self.sources if s.type == "Debrid"],
        }

        if selected_type in one_click_filters:
            filtered_sources = one_click_filters[selected_type]()
            if not filtered_sources:
                kodilog("No sources found matching the filter")
                return
            self.filtered_sources = filtered_sources
            self.filter_applied = True
        elif selected_type in filter_map:
            items = filter_map[selected_type]["items"]()
            if selected_type == "language" and not items:
                notification(translation(90406))
                return
            popup = FilterWindow("filter_items.xml", ADDON_PATH, filter=items)
            popup.doModal()
            selected_filter = popup.selected_filter
            del popup
            if selected_filter is not None:
                filtered_sources = filter_map[selected_type]["filter"](selected_filter)
                if not filtered_sources:
                    kodilog("No sources found matching the filter")
                    return
                self.filtered_sources = filtered_sources
                self.filter_applied = True
            else:
                self.filtered_sources = None
                self.filter_applied = False
        else:
            self.filtered_sources = None
            self.filter_applied = False

        self.populate_sources_list()
        self.set_default_focus(self.display_list, 1000, control_list_reset=True)

    def _handle_context_menu_action(self):
        self.position = self.display_list.getSelectedPosition()
        selected_source = self.list_sources[self.position]

        menu_items = []
        menu_actions = []

        if selected_source.type == IndexerType.TORRENT:
            menu_items.extend([translation(90365), translation(90359), translation(90083)])
            menu_actions.extend(["download_to_debrid", "add_to_torrserver", "download_file"])
        elif selected_source.type in (IndexerType.DIRECT, IndexerType.STREMIO_DEBRID):
            menu_items.extend([translation(90083), translation(90082)])
            menu_actions.extend(["download_file", "subtitle_download"])
        else:
            menu_items.extend([translation(90084), translation(90083), translation(90082)])
            menu_actions.extend(["pack_select", "download_file", "subtitle_download"])

        response = xbmcgui.Dialog().contextmenu(menu_items)
        if response < 0 or response >= len(menu_actions):
            return

        action = menu_actions[response]
        kodilog(
            f"SourceSelect context action selected: action={action}, mode={self.item_information.get('mode')}, query={self.item_information.get('query')}, year={self.item_information.get('year')}"
        )
        if action == "download_to_debrid":
            try:
                self._download_to_debrid(selected_source)
            except Exception as e:
                kodilog(f"SourceSelect _download_to_debrid raised: {e}")
                notification(str(e))
        elif action == "add_to_torrserver":
            self._add_to_torrserver(selected_source)
        elif action == "download_file":
            self._download_file(selected_source)
        elif action == "subtitle_download":
            self._resolve_item(selected_source, is_subtitle_download=True)
        elif action == "pack_select":
            self._resolve_item(selected_source, pack_select=True)

    def _handle_quality_select_action(self):
        quality_list = self.getControl(1300)
        selected_item = quality_list.getSelectedItem()
        if selected_item:
            selected_quality = selected_item.getProperty("quality")
            filtered_sources = [
                s for s in self.sources if selected_quality in s.quality
            ]
            if not filtered_sources:
                kodilog("No sources found matching the filter")
                return
            self.filtered_sources = filtered_sources
            self.filter_applied = True
            self.populate_sources_list()

    def _handle_select_action(self, control_id):
        self.position = self.display_list.getSelectedPosition()
        selected_source = self.list_sources[self.position]

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
            info = parse_title_info(source.title)
            menu_item = xbmcgui.ListItem(label=source.title)
            menu_item.setProperty("title", source.title)
            menu_item.setProperty("display_title", info["clean_title"])
            menu_item.setProperty("codec", info["codec"])
            menu_item.setProperty("audio", info["audio"])
            menu_item.setProperty("hdr_info", info["badges"])
            menu_item.setProperty("release_group", info["release_group"])
            kodilog(f"SourceSelect populate_sources_list: source.type={source.type}")
            if source.type in IndexerType.TORRENT:
                if source.addedToDebrid and source.debridType:
                    provider_name = source.debridType
                else:
                    provider_name = source.type or source.subindexer 
            elif source.type == IndexerType.DEBRID:
                provider_name = source.debridType or source.type 
            elif IndexerType.STREMIO_DEBRID:
                provider_name = source.subindexer or source.type
            elif source.type == IndexerType.DIRECT:
                provider_name = source.indexer or source.type
            else:
                provider_name = source.debridType or source.type
            indexer_label = source.addonInstanceLabel or source.indexer
            menu_item.setProperty("type", get_provider_color(provider_name))
            menu_item.setProperty("indexer", get_random_color(indexer_label))
            menu_item.setProperty("guid", source.guid)
            menu_item.setProperty("infoHash", source.infoHash)
            menu_item.setProperty("size", bytes_to_human_readable(int(source.size)))
            if source.seeders and not source.isCached:
                menu_item.setProperty("seeders", str(source.seeders))
            if source.peers and not source.isCached:
                menu_item.setProperty("peers", str(source.peers))
            menu_item.setProperty(
                "fullLanguages", get_colored_languages(source.fullLanguages)
            )
            menu_item.setProperty("provider", get_random_color(source.provider))
            menu_item.setProperty(
                "publishDate", extract_publish_date(source.publishDate)
            )
            menu_item.setProperty("quality", source.quality)
            menu_item.setProperty("status", get_source_status(source))
            menu_item.setProperty("isPack", str(source.isPack))

            self.display_list.addItem(menu_item)

    def _refresh_sources_list(self) -> None:
        if not hasattr(self, "display_list"):
            return

        current_position = max(getattr(self, "position", 0), 0)
        self.populate_sources_list()
        if self.list_sources:
            self.set_default_focus(self.display_list, 1000, control_list_reset=True)
            self.display_list.selectItem(min(current_position, len(self.list_sources) - 1))

    def _download_to_debrid(self, selected_source) -> None:
        kodilog("SourceSelect _download_to_debrid entered")
        url, magnet, _ = self._extract_source_details(selected_source)
        info_hash = selected_source.infoHash or ""
        torrent_data = b""

        if not info_hash and magnet:
            info_hash = get_info_hash_from_magnet(magnet).lower()

        if not info_hash and url.startswith("magnet:?"):
            info_hash = get_info_hash_from_magnet(url).lower()

        if url:
            kodilog(f"Fetching torrent URL to extract info_hash: {url}")
            torrent_data, magnet_candidate, extracted_hash, torrent_url = (
                get_torrent_data_from_uri(url)
            )
            if magnet_candidate and not magnet:
                magnet = magnet_candidate
            if extracted_hash and not info_hash:
                info_hash = extracted_hash
            if torrent_url:
                selected_source.url = torrent_url

        if not info_hash and not torrent_data:
            notification(translation(90361))
            return

        debrid_type = add_source_to_debrid(
            info_hash,
            selected_source.debridType,
            torrent_data=torrent_data,
            torrent_name=selected_source.title or self.item_information.get("title", ""),
        )
        if debrid_type:
            kodilog(f"SourceSelect download_to_debrid succeeded via {debrid_type}")
            if info_hash:
                selected_source.infoHash = info_hash
            selected_source.debridType = debrid_type
            selected_source.addedToDebrid = True
            self._refresh_sources_list()

    def _add_to_torrserver(self, selected_source) -> None:
        url, magnet, _ = self._extract_source_details(selected_source)
        title = selected_source.title or self.item_information.get("title", "")
        poster = self.item_information.get("poster", "")

        add_source_to_torrserver(
            magnet=magnet,
            url=url,
            info_hash=selected_source.infoHash or "",
            title=title,
            poster=poster,
        )

    def _download_file(self, selected_source) -> None:
        self.playback_info = self._ensure_playback_info(selected_source)
        if self.playback_info:
            self.playback_info.update(self.item_information)
        else:
            notification(translation(90407))
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
                translation(90653), translation(90654) % str(e)
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
        self.resolved = resolver_window.doModal(pack_select)
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
