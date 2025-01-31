import xbmcgui
from typing import List, Dict, Optional
from lib.gui.base_window import BaseWindow
from lib.gui.resolver_window import ResolverWindow
from lib.gui.source_section_manager import (
    SourceSectionManager,
    SourceSection,
    SourceItem,
)
from lib.gui.resume_window import ResumeDialog
from lib.utils.kodi_utils import ADDON_PATH
from lib.api.jacktook.kodi import kodilog


class SourceSelectNew(BaseWindow):
    """Main window for selecting media sources from organized sections."""

    CACHE_KEY_FIELD = "tv_data"  # Fallback to "ids" if not available

    def __init__(
        self,
        xml_layout: str,
        window_location: str,
        item_information: Optional[Dict] = None,
        sources: Optional[List[Dict]] = None,
        uncached: Optional[List[Dict]] = None,
    ):
        super().__init__(xml_layout, window_location, item_information=item_information)

        self._sources = self._preprocess_sources(sources or [])
        self._uncached_sources = uncached or []
        self._item_metadata = item_information or {}
        self._playback_info = None
        self._resume_flag = None

        self._init_ui_properties()
        self._section_manager = self._create_section_manager()

    def _preprocess_sources(self, raw_sources: List[Dict]) -> List[Dict]:
        """Add unique identifiers to sources for tracking."""
        return [dict(source, id=i) for i, source in enumerate(raw_sources)]

    def _init_ui_properties(self) -> None:
        """Initialize default UI state properties."""
        self.setProperty("instant_close", "false")
        self.setProperty("resolving", "false")

    def _create_section_manager(self) -> SourceSectionManager:
        """Organize sources into categorized sections."""
        sections = [
            self._create_priority_language_section(),
            self._create_top_seeders_section(),
            *self._create_provider_sections(),
        ]
        return SourceSectionManager(sections)

    def _create_priority_language_section(self) -> SourceSection:
        """Create section for priority language (Spanish) sources."""
        spanish_sources = [
            s for s in self._sources if "es" in s.get("fullLanguages", [])
        ]
        return SourceSection(
            title="Priority Language",
            description="Sources with Spanish audio",
            sources=[SourceItem.from_source(s) for s in spanish_sources],
        )

    def _create_top_seeders_section(self) -> SourceSection:
        """Create section for sources with highest combined seeders."""
        non_spanish_sources = [
            s for s in self._sources if "es" not in s.get("fullLanguages", [])
        ]
        return SourceSection(
            title="Top Seeders",
            description="Results with the most seeders",
            sources=[SourceItem.from_source(s) for s in non_spanish_sources],
        )

    def _create_provider_sections(self) -> List[SourceSection]:
        """Create sections organized by provider, sorted by total seeders."""
        provider_rankings = self._calculate_provider_seed_rankings()
        return [
            SourceSection(
                title=provider,
                description=f"Sources from {provider} provider",
                sources=[
                    SourceItem.from_source(s)
                    for s in self._sources
                    if s["provider"] == provider
                ],
            )
            for provider in provider_rankings
        ]

    def _calculate_provider_seed_rankings(self) -> List[str]:
        """Calculate provider rankings based on total seeders."""
        seed_sums: Dict[str, int] = {}
        for source in self._sources:
            provider = source["provider"]
            seed_sums[provider] = seed_sums.get(provider, 0) + source.get("seeders", 0)
        return sorted(seed_sums.keys(), key=lambda k: seed_sums[k], reverse=True)

    def onInit(self) -> None:
        """Initialize window controls and populate initial data."""
        self._source_list = self.getControlList(1000)
        self._navigation_label = self.getControl(1001)
        self._description_label = self.getControl(1002)
        self._refresh_ui()
        self.set_default_focus(self._source_list, 1000, control_list_reset=True)
        super().onInit()

    def _refresh_ui(self) -> None:
        """Update all UI elements with current state."""
        self._update_navigation_header()
        self._update_description()
        self._populate_source_list()

    def _update_navigation_header(self) -> None:
        """Update the navigation breadcrumb display."""
        current_index = self._section_manager._current_index
        all_titles = self._section_manager.section_titles

        # Build truncated navigation path
        preceding_titles = all_titles[:current_index]
        if len(preceding_titles) > 2:
            preceding_titles = ["...", *preceding_titles[-2:]]

        navigation_path = [
            *preceding_titles,
            f"[B][COLOR white]{all_titles[current_index]}[/COLOR][/B]",
            *all_titles[current_index + 1 :],
        ]

        self._navigation_label.setLabel(" | ".join(navigation_path))

    def _update_description(self) -> None:
        """Update the section description label."""
        self._description_label.setLabel(
            self._section_manager.current_section.description
        )

    def _populate_source_list(self) -> None:
        """Populate the source list with current section's items."""
        self._source_list.reset()
        current_sources = self._section_manager.current_section.sources
        self._source_list.addItems(current_sources)
        self._source_list.selectItem(
            self._section_manager.current_section.selection_position
        )

    def handle_action(self, action_id: int, control_id: Optional[int] = None) -> None:
        """Handle user input actions."""
        kodilog(f"Action ID: {action_id}, Control ID: {control_id}")
        if control_id == 1000:
            self._handle_source_list_action(action_id)

    def _handle_source_list_action(self, action_id: int) -> None:
        """Process actions specific to the source list control."""
        current_section = self._section_manager.current_section
        current_section.update_selection_position(
            self._source_list.getSelectedPosition()
        )

        action_handlers = {
            xbmcgui.ACTION_SELECT_ITEM: self._resolve_selected_source,
            xbmcgui.ACTION_MOVE_LEFT: self._section_manager.move_to_previous_section,
            xbmcgui.ACTION_MOVE_RIGHT: self._section_manager.move_to_next_section,
            xbmcgui.ACTION_CONTEXT_MENU: self._show_context_menu,
        }

        handler = action_handlers.get(action_id)
        if handler:
            handler()
            self._refresh_ui()

    def _show_context_menu(self) -> None:
        """Display context menu for selected source."""
        source = self._get_source_from_item(
            self._section_manager.current_section.current_source
        )
        menu_options = self._get_context_menu_options(source["type"])

        choice = xbmcgui.Dialog().contextmenu(menu_options)
        if choice == 0:
            self._handle_context_choice(source["type"])

    def _get_context_menu_options(self, source_type: str) -> List[str]:
        """Get available context menu options based on source type."""
        return {
            "Torrent": ["Download to Debrid"],
            "Direct": [],
        }.get(source_type, ["Browse into"])

    def _handle_context_choice(self, source_type: str) -> None:
        """Handle context menu selection."""
        handlers = {
            "Torrent": self._download_to_debrid,
            "Direct": lambda: None,
            "default": self._browse_source_pack,
        }
        handler = handlers.get(source_type, handlers["default"])
        handler()

    def _download_to_debrid(self) -> None:
        """Handle Debrid download request."""
        # Implementation placeholder
        pass

    def _browse_source_pack(self) -> None:
        """Handle pack browsing request."""
        # Implementation placeholder
        pass

    def _resolve_selected_source(self) -> None:
        """Initiate resolution of the selected source."""
        self.setProperty("resolving", "true")
        selected_source = self._get_source_from_item(
            self._section_manager.current_section.current_source
        )

        resolver = ResolverWindow(
            "resolver.xml",
            ADDON_PATH,
            source=selected_source,
            previous_window=self,
            item_information=self._item_metadata,
        )
        resolver.doModal(pack_select=False)
        self._playback_info = resolver.playback_info

        del resolver
        self._close_window()

    def _get_source_from_item(self, source_item: SourceItem) -> Dict:
        """Retrieve original source data from ListItem."""
        source_id = int(source_item.getProperty("id"))
        return next(s for s in self._sources if s["id"] == source_id)

    def _close_window(self) -> None:
        """Close the window and clean up resources."""
        self.setProperty("instant_close", "true")
        self.close()

    def doModal(self) -> Optional[Dict]:
        """Display the window and return playback info when closed."""
        super().doModal()
        return self._playback_info

    def show_resume_dialog(self, playback_percent: float) -> bool:
        """Display resume playback dialog."""
        try:
            resume_dialog = ResumeDialog(
                "resume_dialog.xml",
                ADDON_PATH,
                resume_percent=playback_percent,
            )
            resume_dialog.doModal()
            return resume_dialog.resume
        finally:
            del resume_dialog
