from .enricher import Enricher
import re
from typing import Dict, Set, List


class LanguageEnricher(Enricher):
    def __init__(self, language_map: Dict[str, str], keywords: Set[str]):
        self.flag_regex = re.compile(r"[\U0001F1E6-\U0001F1FF]{2}")
        self.keyword_regex = re.compile(
            r"\b(?:" + "|".join(re.escape(k) for k in keywords) + r")\b", re.IGNORECASE
        )
        self.language_map = language_map

    def initialize(self, items: List[Dict]) -> None:
        return

    def needs(self):
        return ["description", "languages"]
    
    def provides(self):
        return ["languages", "fullLanguages"]

    def enrich(self, item: Dict) -> None:
        desc = item.get("description", "")

        # Flag-based detection
        flags = self.flag_regex.findall(desc)
        flag_langs = {self.language_map.get(f, "") for f in flags}

        # Keyword-based detection
        keywords = self.keyword_regex.findall(desc.lower())
        keyword_langs = {self.language_map.get(k, "") for k in keywords}

        combined = flag_langs | keyword_langs
        item["languages"] = list(combined - {""})
        item["fullLanguages"] = item["languages"].copy()
