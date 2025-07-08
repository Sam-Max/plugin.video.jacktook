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


class BaseProcessBuilder:
    def __init__(self, results: List[TorrentStream]):
        self.results: List[TorrentStream] = results

    def get_season_pack_patterns(self, season_num: int) -> list:
        season_fill = f"{int(season_num):02}"
        return [
            rf"\.S{season_num}\.",
            rf"\.S{season_fill}\.",
            rf"\sS{season_num}\s",
            rf"\sS{season_fill}\s",
            rf"\.{season_num}\.season",
            r"total\.season",
            r"season",
            r"the\.complete",
            r"complete",
            r"integrale",
            rf"Saison {season_num}"
            r"S(\d{2})E(\d{2})-(\d{2})",
            rf"\.season\.{season_num}\.",
            rf"\.season{season_num}\.",
            rf"\.season\.{season_fill}\.",
            rf"s1 to {season_num}",
            rf"s1 to s{season_num}",
            rf"s01 to {season_fill}",
            rf"s01 to s{season_fill}",
            rf"s1 thru {season_num}",
            rf"s1 thru s{season_num}",
            rf"s01 thru {season_fill}",
            rf"s01 thru s{season_fill}",
        ]

    def get_results(self) -> List[TorrentStream]:
        return self.results


class PostProcessBuilder(BaseProcessBuilder):
    def __init__(self, results: List[TorrentStream]):
        super().__init__(results)

    def check_season_pack(self, season: int) -> "PostProcessBuilder":
        season_patterns = self.get_season_pack_patterns(season)
        for res in self.results:
            res.isPack = bool(re.search("|".join(season_patterns), res.title))
        return self

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


class PreProcessBuilder(BaseProcessBuilder):
    def __init__(self, results: List[TorrentStream]):
        super().__init__(results)

    def remove_duplicates(self) -> "PreProcessBuilder":
        seen_values: List[str] = []
        unique_results: List[TorrentStream] = []
        for res in self.results:
            key = getattr(res, "infoHash", None) or getattr(res, "guid", None)
            if key and key not in seen_values:
                unique_results.append(res)
                seen_values.append(key)
        self.results = unique_results
        return self

    def filter_torrent_sources(self) -> "PreProcessBuilder":
        self.results = [res for res in self.results if res.infoHash or res.guid]
        kodilog(f"Filtered torrent sources: {self.results}", level=xbmc.LOGDEBUG)
        return self

    def filter_season_packs(self, season_num: int) -> List[TorrentStream]:
        season_patterns = self.get_season_pack_patterns(season_num)
        return [
            res
            for res in self.results
            if re.search("|".join(season_patterns), res.title)
        ]

    def filter_sources(
        self, episode_name: str, episode_num: int, season_num: int
    ) -> "PreProcessBuilder":

        include_season_packs = get_setting("include_season_packs")
        season_pack_results: List[TorrentStream] = []

        if include_season_packs:
            kodilog("Including season packs in filtering")
            season_pack_results = self.filter_season_packs(season_num)

        episode_fill = f"{int(episode_num):02}"
        season_fill = f"{int(season_num):02}"

        patterns = [
            rf"S{season_fill}E{episode_fill}",  # SXXEXX format
            rf"{season_fill}x{episode_fill}",  # XXxXX format
            rf"\.S{season_fill}E{episode_fill}",  # .SXXEXX format
            rf"\sS{season_fill}E{episode_fill}\s",  # season and episode surrounded by spaces
            r"Cap\.",  # match "Cap."
        ]

        if episode_name:
            patterns.append(episode_name)

        episode_results = [
            res for res in self.results if re.search("|".join(patterns), res.title)
        ]

        # Combine both lists
        self.results = season_pack_results + episode_results

        kodilog(
            f"Filtered by episode and season packs: {self.results}", level=xbmc.LOGDEBUG
        )
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
