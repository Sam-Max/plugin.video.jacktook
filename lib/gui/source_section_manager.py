from lib.utils.kodi_utils import bytes_to_human_readable
from lib.utils.debrid_utils import get_debrid_status
from lib.utils.utils import (
    extract_publish_date,
    get_colored_languages,
    get_random_color,
)
import xbmcgui
from typing import Dict, List


class SourceItem(xbmcgui.ListItem):
    """A custom ListItem representing a media source with formatted properties."""

    @staticmethod
    def from_source(source: Dict) -> "SourceItem":
        """
        Creates a SourceItem from a source dictionary.

        Args:
            source: Dictionary containing source metadata

        Returns:
            Configured SourceItem with formatted properties
        """
        processors = {
            "peers": lambda v, s: v or "",
            "publishDate": lambda v, s: extract_publish_date(v),
            "size": lambda v, s: bytes_to_human_readable(int(v)) if v else "",
            "indexer": lambda v, s: SourceItem._format_colored_text(v),
            "provider": lambda v, s: SourceItem._format_colored_text(v),
            "type": lambda v, s: SourceItem._format_colored_text(v),
            "fullLanguages": lambda v, s: get_colored_languages(v) or "",
        }

        item = SourceItem(label=source["title"])

        item_properties = {
            key: processors.get(key, lambda v, s: v)(value, source)
            for key, value in source.items()
        }

        for key, value in item_properties.items():
            item.setProperty(key, str(value))

        return item

    @staticmethod
    def _format_colored_text(text: str) -> str:
        """Formats text with random color using Kodi markup."""
        color = get_random_color(text)
        return f"[B][COLOR {color}]{text}[/COLOR][/B]"


class SourceSection:
    """Represents a group of media sources with common characteristics."""

    def __init__(self, title: str, description: str, sources: List[SourceItem]):
        self.title = title
        self.description = description
        self.sources = sources
        self.selection_position = 0

    @property
    def current_source(self) -> SourceItem:
        """Get currently selected source in this section."""
        return self.sources[self.selection_position]

    def update_selection_position(self, new_position: int) -> None:
        """Update the selected position in this section's source list."""
        self.selection_position = max(0, min(new_position, len(self.sources) - 1))


class SourceSectionManager:
    """Manages navigation between multiple SourceSections."""

    def __init__(self, sections: List[SourceSection], initial_index: int = 0):
        self._sections = sections
        self._current_index = initial_index

    @property
    def current_section(self) -> SourceSection:
        """Get the currently active section."""
        return self._sections[self._current_index]

    @property
    def section_titles(self) -> List[str]:
        """Get list of all section titles."""
        return [section.title for section in self._sections]

    def move_to_next_section(self) -> None:
        """Advance to the next section in the list."""
        self._current_index = min(self._current_index + 1, len(self._sections) - 1)

    def move_to_previous_section(self) -> None:
        """Return to the previous section in the list."""
        self._current_index = max(self._current_index - 1, 0)

    def jump_to_section(self, section_index: int) -> None:
        """Jump directly to a specific section by index."""
        self._current_index = max(0, min(section_index, len(self._sections) - 1))
