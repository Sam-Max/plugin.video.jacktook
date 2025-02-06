import re


class QualityTier:

    def __init__(self, pattern: str, label: str, label_formatted: str, priority: int):
        self.regex = re.compile(pattern, re.IGNORECASE) if pattern else None
        self.label = label
        self.label_formatted = label_formatted
        self.priority = priority

    @staticmethod
    def default_quality_tiers():
        return [
            QualityTier(
                r"(?i)\b(2160p?|4k)\b", "4k", "[B][COLOR yellow]4k[/COLOR][/B]", 4
            ),
            QualityTier(
                r"(?i)\b(1080p?)\b", "1080p", "[B][COLOR cyan]1080p[/COLOR][/B]", 3
            ),
            QualityTier(
                r"(?i)\b720p?\b", "720p", "[B][COLOR orange]720p[/COLOR][/B]", 2
            ),
            QualityTier(
                r"(?i)\b480p?\b", "480p", "[B][COLOR orange]480p[/COLOR][/B]", 1
            ),
            QualityTier(None, "Other qualities", "[B][COLOR red]N/A[/COLOR][/B]", 0),
        ]
