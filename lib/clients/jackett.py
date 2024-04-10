import requests
from lib.utils.kodi import get_jackett_timeout, notify, translation, log
from lib import xmltodict


class Jackett:
    def __init__(self, host, apikey, notification) -> None:
        self.host = host.rstrip("/")
        self.apikey = apikey
        self._notification = notification

    def search(self, query, mode, season, episode):
        try:
            if mode == "tv":
                url = f"{self.host}/api/v2.0/indexers/all/results/torznab/api?apikey={self.apikey}&t=tvsearch&q={query}&season={season}&ep={episode}"
            elif mode == "movie":
                url = f"{self.host}/api/v2.0/indexers/all/results/torznab/api?apikey={self.apikey}&q={query}"
            elif mode == "multi":
                url = f"{self.host}/api/v2.0/indexers/all/results/torznab/api?apikey={self.apikey}&t=search&q={query}"
            res = requests.get(url, timeout=get_jackett_timeout())
            if res.status_code != 200:
                notify(f"{translation(30229)} ({res.status_code})")
                return
            return self.parse_response(res)
        except Exception as e:
            self._notification(f"{translation(30229)}: {str(e)}")

    def parse_response(self, res):
        res = xmltodict.parse(res.content)
        if "item" in res["rss"]["channel"]:
            item = res["rss"]["channel"]["item"]
            results = []
            for i in item if isinstance(item, list) else [item]:
                extract_result(results, i)
            return results


def extract_result(results, item):
    attributes = {
        attr["@name"]: attr["@value"] for attr in item.get("torznab:attr", [])
    }
    results.append(
        {
            "quality_title": "",
            "title": item.get("title", ""),
            "indexer": item.get("jackettindexer", {}).get("#text", ""),
            "publishDate": item.get("pubDate", ""),
            "guid": item.get("guid", ""),
            "downloadUrl": item.get("link", ""),
            "size": item.get("size", ""),
            "magnetUrl": attributes.get("magneturl", ""),
            "seeders": attributes.get("seeders", ""),
            "peers": attributes.get("peers", ""),
            "infoHash": attributes.get("infohash", ""),
            "debridType": "",
            "debridCached": False,
            "debridPack": False,
        }
    )
