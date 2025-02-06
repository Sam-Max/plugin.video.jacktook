import xbmcgui
from typing import List, Dict, Optional
from lib.gui.base_window import BaseWindow
from lib.gui.source_section_manager import (
    SourceSectionManager,
    SourceSection,
    SourceItem,
)
from lib.api.jacktook.kodi import kodilog
from lib.domain.quality_tier import QualityTier
from lib.services.filters import FilterBuilder
from lib.clients.debrid.transmission import TransmissionClient
from lib.clients.debrid.torrserve import TorrServeClient
from lib.utils.kodi_utils import get_setting
from lib.domain.source import Source


class SourceSelectWindow(BaseWindow):
    """Media source selection window with categorized sections."""

    CACHE_KEY_FIELD = "tv_data"
    SOURCE_ITEM_ID = 1000
    NAVIGATION_LABEL_ID = 1001
    DESCRIPTION_LABEL_ID = 1002
    SETTINGS_GROUP_ID = 2000
    SETTINGS_FIRST_ID = 2002

    def __init__(
        self,
        xml_layout: str,
        window_location: str,
        item_information: Optional[Dict] = None,
        get_sources=None,
    ):
        super().__init__(xml_layout, window_location, item_information=item_information)
        self._item_metadata = item_information or {}
        self._get_sources = get_sources
        self._source: Optional[Source] = None
        self._sources: Optional[List[Source]] = []
        self._navigation_label: Optional[xbmcgui.ControlLabel] = None
        self.setProperty("instant_close", "true")

    def _create_sections(self) -> SourceSectionManager:
        """Create organized source sections."""
        sections = [
            self._create_language_section("Spanish", "es"),
            *self._create_quality_sections(),
        ]
        return SourceSectionManager([s for s in sections if s])

    def _create_language_section(self, lang: str, code: str) -> Optional[SourceSection]:
        """Create section for specific language sources."""
        sources = [s for s in self._sources if code in s.get("languages", [])]
        if not sources:
            return None

        return SourceSection(
            title=f"Priority Language ({len(sources)})",
            description=f"Sources with {lang} audio",
            sources=[SourceItem.from_source(s) for s in sources],
        )

    def _create_quality_sections(self) -> List[SourceSection]:
        """Generate quality tier sections."""
        return [
            SourceSection(
                title=f"{tier.label} ({len(sources)})",
                description=f"{tier.label_formatted} resolution sources",
                sources=[SourceItem.from_source(s) for s in sources],
            )
            for tier in QualityTier.default_quality_tiers()
            if (
                sources := FilterBuilder()
                .filter_by_quality(tier.priority)
                .build(self._sources)
            )
        ]

    def onInit(self) -> None:
        """Initialize window and populate data."""
        self.setProperty("instant_close", "true")

        self._source_list = self.getControlList(self.SOURCE_ITEM_ID)
        self._navigation_label = self.getControl(self.NAVIGATION_LABEL_ID)
        self._description_label = self.getControl(self.DESCRIPTION_LABEL_ID)
        self._settings_first = self.getControl(self.SETTINGS_FIRST_ID)

        super().onInit()

        sources = self._get_sources()
        for i, source in enumerate(sources):
            source["correlative_id"] = i

        self._sources = sources
        self._refresh_ui()

    def _refresh_ui(self) -> None:
        """Update all UI components."""
        self.section_manager = self._create_sections()
        self._navigation_label.setLabel(self._build_navigation_path())
        self._description_label.setLabel(
            self.section_manager.current_section.description
        )
        self._source_list.reset()
        self._source_list.addItems(self.section_manager.current_section.sources)
        self.set_default_focus(self._source_list)
        self.setProperty("instant_close", "false")

    def _build_navigation_path(self) -> str:
        """Create truncated navigation breadcrumb."""
        titles = self.section_manager.section_titles
        current_idx = self.section_manager._current_index

        preceding = titles[:current_idx]
        if len(preceding) > 2:
            preceding = ["...", *preceding[-2:]]

        return " | ".join(
            [
                *preceding,
                f"[B][COLOR white]{titles[current_idx]}[/COLOR][/B]",
                *titles[current_idx + 1 :],
            ]
        )

    def handle_action(self, action_id: int, control_id: Optional[int] = None) -> None:
        """Route user actions to appropriate handlers."""
        if control_id is None:
            return
        elif control_id == self.SOURCE_ITEM_ID:
            self._handle_list_action(action_id)
        elif control_id >= self.SETTINGS_GROUP_ID:
            self._handle_settings_action(action_id)

    def _handle_list_action(self, action_id: int) -> None:
        """Process source list interactions."""
        actions = {
            xbmcgui.ACTION_SELECT_ITEM: self._resolve_source,
            xbmcgui.ACTION_MOVE_LEFT: self._handle_navigation_left,
            xbmcgui.ACTION_MOVE_RIGHT: self.section_manager.move_to_next_section,
            xbmcgui.ACTION_CONTEXT_MENU: self._show_context_menu,
        }
        if handler := actions.get(action_id):
            handler()
            self._refresh_ui()

    def _handle_settings_action(self, action_id: int) -> None:
        """Process settings interactions."""
        if action_id == xbmcgui.ACTION_MOVE_RIGHT:
            self.setProperty("settings_open", "false")
            self.setFocus(self._source_list)

    def _handle_navigation_left(self) -> None:
        """Handle left navigation between sections/settings."""
        if self.section_manager._current_index > 0:
            self.section_manager.move_to_previous_section()
        else:
            self.setProperty("settings_open", "true")
            self.setFocus(self._settings_first)

    def _resolve_source(self) -> None:
        """Initiate playback resolution for selected source."""
        source = self._get_selected_source()
        self._source = source
        self.close()

        # resolver = ResolverWindow(
        #     "resolver.xml", ADDON_PATH,
        #     source=source,
        #     item_information=self._item_metadata,
        #     previous_window=self
        # )
        # resolver.doModal()
        # self._playback_info = resolver.playback_info
        # self.close()

    def _show_context_menu(self) -> None:
        """Display context options for selected source."""
        source = self._get_selected_source()

        options = {
            "Torrent": [
                "Download to Debrid",
                "Download to Transmission",
                "Download to TorrServer",
            ],
            "Direct": [],
        }.get(source["type"], ["Browse into"])

        choice = xbmcgui.Dialog().contextmenu(options)
        if choice == 1:
            TransmissionClient(
                get_setting("transmission_host"),
                get_setting("transmission_folder"),
                get_setting("transmission_user"),
                get_setting("transmission_pass"),
            ).add_magnet(source["magnet"])
        elif choice == 2:
            kodilog("TorrServeClient().add_magnet")
            TorrServeClient().add_magnet(source["magnet"])

    def _get_selected_source(self) -> Source:
        """Retrieve currently selected source data."""

        return self._sources[
            int(self._source_list.getSelectedItem().getProperty("correlative_id"))
        ]

    def doModal(self) -> Optional[Source]:
        """Show window and return playback info on close."""
        super().doModal()
        return self._source
