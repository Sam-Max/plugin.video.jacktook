import re
from typing import List, Any, Union
from lib.domain.source import Source
from lib.domain.interface.filter_interface import FilterInterface



class FieldFilter(FilterInterface):
    def __init__(self, field: str, value: Any):
        self.field = field
        self.value = value

    def matches(self, item: Source) -> bool:
        return item.get(self.field) == self.value
    
    def reset(self):
        pass


class DedupeFilter(FilterInterface):
    def __init__(self):
        self.seen = set()

    def matches(self, item: Source) -> bool:
        info_hash = item.get("info_hash")
        if info_hash in self.seen:
            return False
        if info_hash is not None:
            self.seen.add(info_hash)
        return True

    def reset(self):
        self.seen.clear()


class SourceFilter(FilterInterface):
    def matches(self, item: Source) -> bool:
        return bool(item.get("info_hash") or item.get("guid"))


class LanguageFilter(FilterInterface):
    def __init__(self, languages: List[str]):
        self.languages = languages

    def matches(self, item: Source) -> bool:
        if not self.languages:
            return True
        item_langs = item.get("languages", [])
        return any(lang in item_langs for lang in self.languages)


class EpisodeFilter(FilterInterface):
    def __init__(self, episode_name: str, episode_num: int, season_num: int):
        self.episode_name = episode_name
        self.episode_num = episode_num
        self.season_num = season_num
        self.compiled_pattern = self._compile_pattern()

    def _compile_pattern(self):
        episode_fill = f"{self.episode_num:02d}"
        season_fill = f"{self.season_num:02d}"

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

        return re.compile("|".join(patterns), flags=re.IGNORECASE)

    def matches(self, item: Source) -> bool:
        title = item.get("title", "")
        return bool(self.compiled_pattern.search(title))


class FilterBuilder(FilterInterface):
    def __init__(self, operator: str = "AND"):
        self._filters: List[FilterInterface] = []
        self._operator = operator.upper()
        self._sort_criteria: List[tuple] = []
        self._limit: int = 0

    def matches(self, item: Source) -> bool:
        if not self._filters:
            return True

        results = [f.matches(item) for f in self._filters]
        if self._operator == "AND":
            return all(results)
        elif self._operator == "OR":
            return any(results)
        else:
            raise ValueError(f"Invalid operator: {self._operator}. Use 'AND' or 'OR'.")

    def reset(self):
        for f in self._filters:
            f.reset()

    def sort_by(self, field: str, ascending: bool = True) -> "FilterBuilder":
        self._sort_criteria.append((field, ascending))
        return self

    def limit(self, n: int) -> "FilterBuilder":
        self._limit = n
        return self

    def filter_by_field(self, field: str, value: Any) -> "FilterBuilder":
        self._filters.append(FieldFilter(field, value))
        return self
    
    def filter_by_quality(self, priority: int) -> "FilterBuilder":
        self._filters.append(FieldFilter("quality_sort", priority))
        return self

    def filter_by_language(self, language_code: str) -> "FilterBuilder":
        existing = next((f for f in self._filters if isinstance(f, LanguageFilter)), None)
        if existing:
            existing.languages.append(language_code)
        else:
            self._filters.append(LanguageFilter([language_code]))
        return self

    def dedupe_by_infoHash(self) -> "FilterBuilder":
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
        self._filters = [f for f in self._filters if not isinstance(f, EpisodeFilter)]
        self._filters.append(EpisodeFilter(episode_name, episode_num, season_num))
        return self

    def filter_by_source(self) -> "FilterBuilder":
        if not any(isinstance(f, SourceFilter) for f in self._filters):
            self._filters.append(SourceFilter())
        return self

    def add_filter(self, filter: FilterInterface) -> "FilterBuilder":
        self._filters.append(filter)
        return self

    def build(self, items: List[Source]) -> List[Source]:
        self.reset()
        filtered_items = [item for item in items if self.matches(item)]
        sorted_items = self._apply_sorting(filtered_items)
        limited_items = self._apply_limit(sorted_items)
        return limited_items

    def _apply_sorting(self, items: List[Source]) -> List[Source]:
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

    def _apply_limit(self, items: List[Source]) -> List[Source]:
        return items[: self._limit] if self._limit else items