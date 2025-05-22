from enum import Enum
import re
from typing import List, Dict
from lib.utils.kodi.utils import get_setting, kodilog
from lib.clients.base import TorrentStream

import xbmc

class Quality(Enum):
    LOW = ("480p", "[B][COLOR orange]480p[/COLOR][/B]")
    MEDIUM = ("720p", "[B][COLOR orange]720p[/COLOR][/B]")
    HIGH = ("1080p", "[B][COLOR blue]1080p[/COLOR][/B]")
    ULTRA = ("2160", "[B][COLOR yellow]4k[/COLOR][/B]")
    UNKNOWN = ("N/A", "[B][COLOR yellow]N/A[/COLOR][/B]")


class SortField(Enum):
    SEEDS = "seeders"
    SIZE = "size"
    DATE = "publishDate"
    QUALITY = "quality"
    CACHED = "isCached"


class PostProcessBuilder:
    def __init__(self, results: List[TorrentStream]):
        self.results: List[TorrentStream] = results

    def check_season_pack(self, season: int) -> "PostProcessBuilder":
        season_patterns = self._generate_season_patterns(season)
        for res in self.results:
            res.isPack = self._matches_any_pattern(res.title, season_patterns)
        return self

    def _generate_season_patterns(self, season_num: int) -> List[str]:
        season_fill = f"{int(season_num):02}"

        return [
            # Season as ".S{season_num}." or ".S{season_fill}."
            rf"\.S{season_num}\.",
            rf"\.S{season_fill}\.",
            # Season as " S{season_num} " or " S{season_fill} "
            rf"\sS{season_num}\s",
            rf"\sS{season_fill}\s",
            # Season as ".{season_num}.season" (like .1.season, .01.season)
            rf"\.{season_num}\.season",
            # "total.season" or "season" or "the.complete"
            r"total\.season",
            r"season",
            r"the\.complete",
            r"complete",
            # Pattern to detect episode ranges like S02E01-02
            r"S(\d{2})E(\d{2})-(\d{2})",
            # Season as ".season.{season_num}." or ".season.{season_fill}."
            rf"\.season\.{season_num}\.",
            rf"\.season{season_num}\.",
            rf"\.season\.{season_fill}\.",
            # Handle cases "s1 to {season_num}", "s1 thru {season_num}", etc.
            rf"s1 to {season_num}",
            rf"s1 to s{season_num}",
            rf"s01 to {season_fill}",
            rf"s01 to s{season_fill}",
            rf"s1 thru {season_num}",
            rf"s1 thru s{season_num}",
            rf"s01 thru {season_fill}",
            rf"s01 thru s{season_fill}",
        ]

    def _matches_any_pattern(self, title: str, patterns: List[str]) -> bool:
        combined_pattern = "|".join(patterns)
        return bool(re.search(combined_pattern, title))

    def sort_results(self) -> "PostProcessBuilder":
        sort_by = get_setting("indexers_sort_by")
        if sort_by in SortField.__members__:
            self.results = sorted(
                self.results,
                key=lambda r: getattr(r, SortField[sort_by].value, 0),
                reverse=True,
            )
        return self

    def limit_results(self) -> "PostProcessBuilder":
        limit = int(get_setting("indexers_total_results"))
        self.results = self.results[:limit]
        return self

    def remove_duplicates(self) -> "PostProcessBuilder":
        seen_values: List[str] = []
        unique_results: List[TorrentStream] = []
        for res in self.results:
            if res.infoHash not in seen_values:
                unique_results.append(res)
                seen_values.append(res.infoHash)
        self.results = unique_results
        return self

    def get_results(self) -> List[TorrentStream]:
        return self.results


class PreProcessBuilder:
    def __init__(self, results: List[TorrentStream]):
        self.results: List[TorrentStream] = results

    def remove_duplicates(self) -> "PreProcessBuilder":
        seen_values: List[str] = []
        unique_results: List[TorrentStream] = []
        for res in self.results:
            if res.infoHash not in seen_values or res.guid not in seen_values:
                unique_results.append(res)
                seen_values.append(res.infoHash)
                seen_values.append(res.guid)
        self.results = unique_results
        kodilog(f"Removed duplicates: {self.results}", level=xbmc.LOGDEBUG)
        return self

    def filter_torrent_sources(self) -> "PreProcessBuilder":
        self.results = [res for res in self.results if res.infoHash or res.guid]
        kodilog(f"Filtered torrent sources: {self.results}", level=xbmc.LOGDEBUG)
        return self

    def filter_by_episode(
        self, episode_name: str, episode_num: int, season_num: int
    ) -> "PreProcessBuilder":
        episode_fill = f"{int(episode_num):02}"
        season_fill = f"{int(season_num):02}"

        patterns = [
            rf"S{season_fill}E{episode_fill}",  # SXXEXX format
            rf"{season_fill}x{episode_fill}",  # XXxXX format
            rf"\s{season_fill}\s",  # season surrounded by spaces
            rf"\.S{season_fill}",  # .SXX format
            rf"\.S{season_fill}E{episode_fill}",  # .SXXEXX format
            rf"\sS{season_fill}E{episode_fill}\s",  # season and episode surrounded by spaces
            r"Cap\.",  # match "Cap."
        ]

        if episode_name:
            patterns.append(episode_name)

        combined_pattern = "|".join(patterns)
        self.results = [
            res for res in self.results if re.search(combined_pattern, res.title)
        ]
        kodilog(f"Filtered by episode: {self.results}", level=xbmc.LOGDEBUG)
        return self

    def filter_by_quality(self) -> "PreProcessBuilder":
        quality_buckets: Dict[Quality, List[TorrentStream]] = {
            quality: [] for quality in Quality
        }

        for res in self.results:
            kodilog(f"Processing result: {res.title}", level=xbmc.LOGDEBUG)
            title = res.title
            matched_quality = False
            for quality in Quality:
                if quality.value[0] in title:
                    res.quality = quality.value[1]
                    quality_buckets[quality].append(res)
                    matched_quality = True
                    break
            if not matched_quality:
                res.quality = Quality.UNKNOWN.value[1]
                quality_buckets[Quality.UNKNOWN].append(res)

        self.results = (
            quality_buckets[Quality.ULTRA]
            + quality_buckets[Quality.HIGH]
            + quality_buckets[Quality.MEDIUM]
            + quality_buckets[Quality.LOW]
            + quality_buckets[Quality.UNKNOWN]
        )

        kodilog(f"Quality buckets: {self.results}", level=xbmc.LOGDEBUG)

        return self

    def get_results(self) -> List[TorrentStream]:
        return self.results
