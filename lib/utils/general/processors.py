from enum import Enum
import re
from typing import List, Dict, Optional

from lib.utils.kodi.utils import get_setting, kodilog
from lib.clients.base import TorrentStream


class Quality(Enum):
    LOW = ("480p", "[B][COLOR orange]480p[/COLOR][/B]")
    MEDIUM = ("720p", "[B][COLOR orange]720p[/COLOR][/B]")
    HIGH = ("1080p", "[B][COLOR blue]1080p[/COLOR][/B]")
    ULTRA = ("2160", "[B][COLOR yellow]4k[/COLOR][/B]")
    UNKNOWN = ("N/A", "[B][COLOR yellow]N/A[/COLOR][/B]")


class SourceCategory(Enum):
    BLURAY_UHD = (
        "BluRay/UHD",
        [
            "BluRay",
            "BluRay REMUX",
            "BRRip",
            "BDRip",
            "UHDRip",
            "REMUX",
            "BLURAY",
            "DolbyVision",
            "HDR10",
        ],
    )
    WEB_HD = (
        "WEB/HD",
        [
            "WEB-DL",
            "WEB-DLRip",
            "WEBRip",
            "HDRip",
            "WEBMux",
            "AMZN",
        ],
    )
    DVD_TV_SAT = (
        "DVD/TV/SAT",
        ["DVD", "DVDRip", "HDTV", "SATRip", "TVRip", "PPVRip", "PDTV", "DVDR", "DVD-R"],
    )
    CAM_SCREENER = (
        "CAM/Screener",
        ["CAM", "CAMRip", "SCREENER", "TeleSync", "TeleCine", "SCR"],
    )
    UNKNOWN = ("Unknown", [None])


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
            rf"Saison {season_num}" r"S(\d{2})E(\d{2})-(\d{2})",
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
        limit = int(get_setting("indexers_total_results", 10))
        self.results = self.results[:limit]
        return self


class PreProcessBuilder(BaseProcessBuilder):
    def __init__(self, results: List[TorrentStream]):
        super().__init__(results)

    def remove_duplicates(self) -> "PreProcessBuilder":
        seen_values: List[str] = []
        unique_results: List[TorrentStream] = []
        for res in self.results:
            key = (
                getattr(res, "infoHash", None)
                or getattr(res, "title", None)
                or getattr(res, "guid", None)
            )
            if key and key not in seen_values:
                unique_results.append(res)
                seen_values.append(key)
        self.results = unique_results
        return self

    def filter_torrent_sources(self) -> "PreProcessBuilder":
        self.results = [res for res in self.results if res.infoHash or res.guid]
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
        self.results = season_pack_results + episode_results
        return self

    def filter_by_quality(self) -> "PreProcessBuilder":
        quality_buckets: Dict[Quality, List[TorrentStream]] = {
            quality: [] for quality in Quality
        }
        for res in self.results:
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
        return self

    def filter_by_source(self) -> "PreProcessBuilder":
        """
        Categorize torrents into SourceCategory buckets and filter them
        depending on Kodi settings (quality_filter group).
        """
        source_buckets: Dict[SourceCategory, List[TorrentStream]] = {
            cat: [] for cat in SourceCategory
        }

        for res in self.results:
            title = res.title.upper()
            matched_category = None
            for cat in SourceCategory:
                for keyword in cat.value[1]:
                    if keyword and keyword.upper() in title:
                        source_buckets[cat].append(res)
                        matched_category = cat
                        break
                if matched_category:
                    break
            if not matched_category:
                source_buckets[SourceCategory.UNKNOWN].append(res)

        allowed_results: List[TorrentStream] = []
        if get_setting("bluray_hd_enabled", True):
            allowed_results.extend(source_buckets[SourceCategory.BLURAY_UHD])
        if get_setting("web_hd_enabled", True):
            allowed_results.extend(source_buckets[SourceCategory.WEB_HD])
        if get_setting("dvd_tv_enabled", True):
            allowed_results.extend(source_buckets[SourceCategory.DVD_TV_SAT])
        if get_setting("cam_screener_enabled", True):
            allowed_results.extend(source_buckets[SourceCategory.CAM_SCREENER])
        if get_setting("unknown_enabled", True):
            allowed_results.extend(source_buckets[SourceCategory.UNKNOWN])

        self.results = allowed_results
        return self

    def filter_by_size(self) -> "PreProcessBuilder":
        min_size = int(get_setting("minimum_size") or 0)
        max_size = int(get_setting("maximum_size") or 100000)

        def parse_size(res: TorrentStream) -> Optional[int]:
            size_bytes = getattr(res, "size", None)
            if size_bytes is None:
                return None
            try:
                return int(size_bytes) // (1024 * 1024)  # Convert bytes → MB
            except (ValueError, TypeError):
                return None

        filtered = []
        for res in self.results:
            size = parse_size(res)
            if size is not None and min_size <= size <= max_size:
                filtered.append(res)

        self.results = filtered
        return self
