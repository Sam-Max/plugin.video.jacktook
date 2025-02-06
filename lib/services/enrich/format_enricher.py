from lib.domain.interface.enricher_interface import EnricherInterface
from typing import List
from lib.domain.source import Source
import math

# from lib.utils.debrid_utils import get_debrid_status
from lib.utils.utils import (
    # extract_publish_date,
    get_random_color,
)


class FormatEnricher(EnricherInterface):
    def __init__(self):
        pass

    def initialize(self, items: List[Source]) -> None:
        return

    def needs(self):
        return ["is_cached", "cached_sources"]

    def provides(self):
        return ["status", "a1", "a2", "a3", "b1", "b2", "b3"]

    def enrich(self, item: Source) -> None:
        # Extract cache-related information if available
        if item.get("is_cached") and item.get("cache_sources"):
            cache_sources = item.get("cache_sources", [])
            
            # Separate instant availability and non-instant availability sources
            cached_sources = [source for source in cache_sources if source.get("instant_availability")]
            caching_sources = [source for source in cache_sources if not source.get("instant_availability")]

            # Build status message for cached and caching sources
            status_parts = []
            if cached_sources:
                cached_providers = ", ".join(
                    source.get("cache_provider_name", "Unknown") for source in cached_sources
                )
                status_parts.append(f"Cached in {cached_providers}")

            if caching_sources:
                caching_providers = ", ".join(
                    f"{source.get('cache_provider_name', 'Unknown')} ({round(source.get('ratio', 0) * 100)}%)"
                    for source in caching_sources
                )
                status_parts.append(f"Caching in {caching_providers}")

            # Combine status parts into a single string
            item["status"] = ", ".join(status_parts)

        # Update additional fields
        item.update({
            "a1": str(item.get("seeders", "")),  # Seeders count (default to empty string if missing)
            "a2": (
                self._bytes_to_human_readable(item.get("size"))
                if item.get("size") is not None
                else ""
            ),  # Human-readable size (default to empty string if missing)
            "a3": "Torrent",  # Quality formatted (default to empty string if missing)
            "b1": item.get("title", ""),  # Title (default to empty string if missing)
            "b2": self._colored_list(
                [item.get("quality_formatted", "")] + item.get("languages", []) + [item.get("indexer", "")] + [item.get("provider", "")]
            ),  # Colored list of languages, indexer, and provider
            "b3": item.get("status", ""),  # Status (default to empty string if missing)
        })

    def _format_colored_text(self, text: str) -> str:
        """Formats text with random color using Kodi markup."""
        color = get_random_color(text)
        return f"[COLOR {color}]{text}[/COLOR]"

    def _colored_list(self, languages):
        if not languages:
            return ""
        colored_languages = []
        for lang in languages:
            if not lang:
                continue
            lang_color = get_random_color(lang)
            colored_lang = f"[[COLOR {lang_color}]{lang}[/COLOR]]"
            colored_languages.append(colored_lang)
        colored_languages = " ".join(colored_languages)
        return colored_languages

    def _format_significant(self, size, digits=3):
        if size == 0:
            return "0"  # Handle zero case

        order = math.floor(math.log10(abs(size)))  # Get the order of magnitude
        factor = 10 ** (digits - 1 - order)  # Compute scaling factor
        rounded = round(size * factor) / factor  # Round to significant digits
        
        return str(rounded)

    def _bytes_to_human_readable(self, size, unit="B"):
        units = {"B": 0, "KB": 1, "MB": 2, "GB": 3, "TB": 4, "PB": 5}

        while size >= 1000 and unit != "PB":
            size /= 1000
            unit = list(units.keys())[list(units.values()).index(units[unit] + 1)]

        
        return f"{self._format_significant(size, 3)} {unit}"
