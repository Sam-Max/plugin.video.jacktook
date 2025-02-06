from lib.domain.interface.enricher_interface import EnricherInterface
from typing import List
from lib.domain.source import Source
from lib.utils.kodi_formats import is_video


class FileEnricher(EnricherInterface):
    def __init__(self):
        pass

    def initialize(self, items: List[Source]) -> None:
        return

    def needs(self):
        return ["description"]

    def provides(self):
        return ["title", "file", "folder"]

    def enrich(self, item: Source) -> None:
        description = item.get("description", "").splitlines()
        if len(description) > 1 and is_video(description[1]):
            item["title"] = description[1]
            item["file"] = description[1]
            item["folder"] = description[0]
        else:
            item["title"] = description[0]
            item["file"] = description[0]
            item["folder"] = ""
