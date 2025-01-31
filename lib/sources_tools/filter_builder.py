import re
from typing import List, Dict, Any, Union


class FilterBuilder:
    def __init__(self, items: List[Dict[str, Any]]):
        self.items = items
        self._sort_criteria: List[tuple] = []
        self._limit: int = 0
        self._language_filters: List[str] = []
        self._episode_name: Union[str, None] = None
        self._episode_num: Union[int, None] = None
        self._season_num: Union[int, None] = None
        self._filter_sources: bool = False  # New flag for source filtering

    def sort_by(self, field: str, ascending: bool = True) -> "FilterBuilder":
        self._sort_criteria.append((field, ascending))
        return self

    def limit(self, n: int) -> "FilterBuilder":
        self._limit = n
        return self

    def filter_by_language(self, language_code: str) -> "FilterBuilder":
        self._language_filters.append(language_code)
        return self

    def filter_by_episode(
        self,
        episode_name: str,
        episode_num: Union[int, str],
        season_num: Union[int, str],
    ) -> "FilterBuilder":
        self._episode_name = episode_name
        self._episode_num = int(episode_num)
        self._season_num = int(season_num)
        return self

    # New method for source filtering
    def filter_by_source(self) -> "FilterBuilder":
        self._filter_sources = True
        return self

    def build(self) -> List[Dict[str, Any]]:
        filtered = self._apply_filters()
        sorted_items = self._apply_sorting(filtered)
        return self._apply_limit(sorted_items)

    def _apply_filters(self) -> List[Dict[str, Any]]:
        # Remove duplicates first (order-preserving)
        seen = []
        filtered = []
        for item in self.items:
            if item not in seen:
                filtered.append(item)
                seen.append(item)

        # Apply source filter if enabled
        if self._filter_sources:
            filtered = [
                item for item in filtered if item.get("infoHash") or item.get("guid")
            ]

        # Apply language filters (OR logic)
        if self._language_filters:
            filtered = [
                item
                for item in filtered
                if any(
                    lang in item.get("languages", []) for lang in self._language_filters
                )
            ]

        # Apply episode filter
        if self._episode_num is not None and self._season_num is not None:
            episode_fill = f"{self._episode_num:02d}"
            season_fill = f"{self._season_num:02d}"

            patterns = [
                rf"S{season_fill}E{episode_fill}",  # SXXEXX
                rf"{season_fill}x{episode_fill}",  # XXxXX
                rf"\s{season_fill}\s",  # Space-padded season
                rf"\.S{season_fill}",  # .SXX
                rf"\.S{season_fill}E{episode_fill}",  # .SXXEXX
                rf"\sS{season_fill}E{episode_fill}\s",  # Space-padded SXXEXX
                r"Cap\.",  # Cap. prefix
            ]

            if self._episode_name:
                patterns.append(re.escape(self._episode_name))

            combined_pattern = re.compile("|".join(patterns), flags=re.IGNORECASE)
            filtered = [
                item
                for item in filtered
                if combined_pattern.search(item.get("title", ""))
            ]

        return filtered

    def _apply_sorting(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not self._sort_criteria:
            return items

        def sort_key(item):
            key = []
            for field, ascending in self._sort_criteria:
                value = item.get(field)
                # Handle numeric fields with descending support
                if isinstance(value, (int, float)):
                    key.append(-value if not ascending else value)
                # Handle string fields (lexicographic sorting)
                elif isinstance(value, str):
                    key.append(value.lower() if ascending else value.lower()[::-1])
                else:
                    key.append(value)
            return tuple(key)

        try:
            result = sorted(items, key=sort_key)
            return result
        except TypeError:
            pass

        return items

    def _apply_limit(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return items[: self._limit] if self._limit else items
