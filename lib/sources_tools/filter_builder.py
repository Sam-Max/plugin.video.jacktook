import re
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Union


class Filter(ABC):
    @abstractmethod
    def apply(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        pass


class DedupeFilter(Filter):
    def apply(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        filtered = []
        
        for item in items:
            info_hash = item.get("infoHash")
            if info_hash not in seen:
                if info_hash is not None:
                    seen.add(info_hash)
                filtered.append(item)
        
        return filtered


class SourceFilter(Filter):
    def apply(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [item for item in items if item.get("infoHash") or item.get("guid")]


class LanguageFilter(Filter):
    def __init__(self, languages: List[str]):
        self.languages = languages

    def apply(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not self.languages:
            return items
        return [
            item for item in items
            if any(lang in item.get("languages", []) for lang in self.languages)
        ]


class EpisodeFilter(Filter):
    def __init__(self, episode_name: str, episode_num: int, season_num: int):
        self.episode_name = episode_name
        self.episode_num = episode_num
        self.season_num = season_num

    def apply(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        episode_num = self.episode_num
        season_num = self.season_num

        if episode_num is None or season_num is None:
            return items

        episode_fill = f"{episode_num:02d}"
        season_fill = f"{season_num:02d}"

        patterns = [
            rf"S{season_fill}E{episode_fill}",
            rf"{season_fill}x{episode_fill}",
            rf"\s{season_fill}\s",
            rf"\.S{season_fill}",
            rf"\.S{season_fill}E{episode_fill}",
            rf"\sS{season_fill}E{episode_fill}\s",
            r"Cap\.",
        ]

        if self.episode_name:
            patterns.append(re.escape(self.episode_name))

        combined_pattern = re.compile("|".join(patterns), flags=re.IGNORECASE)
        return [
            item for item in items
            if combined_pattern.search(item.get("title", ""))
        ]


class FilterBuilder:
    def __init__(self):
        self._filters: List[Filter] = []
        self._sort_criteria: List[tuple] = []
        self._limit: int = 0

    def sort_by(self, field: str, ascending: bool = True) -> "FilterBuilder":
        self._sort_criteria.append((field, ascending))
        return self

    def limit(self, n: int) -> "FilterBuilder":
        self._limit = n
        return self

    def filter_by_language(self, language_code: str) -> "FilterBuilder":
        existing = next((f for f in self._filters if isinstance(f, LanguageFilter)), None)
        if existing:
            existing.languages.append(language_code)
        else:
            self._filters.append(LanguageFilter([language_code]))
        return self

    def deduple_by_infoHash(self) -> "FilterBuilder":
        self.add_filter(DedupeFilter())
        return self

    def filter_by_episode(
        self,
        episode_name: str,
        episode_num: Union[int, str],
        season_num: Union[int, str],
    ) -> "FilterBuilder":
        episode_num = int(episode_num)
        season_num = int(season_num)
        # Remove any existing EpisodeFilter
        self._filters = [f for f in self._filters if not isinstance(f, EpisodeFilter)]
        self._filters.append(EpisodeFilter(episode_name, episode_num, season_num))
        return self

    def filter_by_source(self) -> "FilterBuilder":
        if not any(isinstance(f, SourceFilter) for f in self._filters):
            self._filters.append(SourceFilter())
        return self

    def add_filter(self, filter: Filter) -> "FilterBuilder":
        self._filters.append(filter)
        return self

    def build(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        filtered_items = items.copy()
        for filter in self._filters:
            filtered_items = filter.apply(filtered_items)

        sorted_items = self._apply_sorting(filtered_items)
        limited_items = self._apply_limit(sorted_items)
        return limited_items

    def _apply_sorting(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not self._sort_criteria:
            return items

        def sort_key(item):
            key = []
            for field, ascending in self._sort_criteria:
                value = item.get(field)
                if isinstance(value, (int, float)):
                    key.append(-value if not ascending else value)
                elif isinstance(value, str):
                    key.append(value.lower() if ascending else value.lower()[::-1])
                else:
                    key.append(value)
            return tuple(key)

        try:
            return sorted(items, key=sort_key)
        except TypeError:
            return items

    def _apply_limit(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return items[: self._limit] if self._limit else items