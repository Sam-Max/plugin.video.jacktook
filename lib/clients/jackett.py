from lib.clients.base import BaseClient
from lib.utils.kodi_utils import translation
from lib import xmltodict
from lib.utils.settings import get_jackett_timeout


class Jackett(BaseClient):
    def __init__(self, host, apikey, notification):
        super().__init__(host, notification)
        self.apikey = apikey
        self.base_url = f"{self.host}/api/v2.0/indexers/all/results/torznab/api?apikey={self.apikey}"

    def search(self, query, mode, season, episode):
        try:
            if mode == "tv":
                url = f"{self.base_url}&t=tvsearch&q={query}&season={season}&ep={episode}"
            elif mode == "movies":
                url = f"{self.base_url}&q={query}"
            else:
                url = f"{self.base_url}&t=search&q={query}"

            response = self.session.get(
                url,
                timeout=get_jackett_timeout(),
            )

            if response.status_code != 200:
                self.notification(f"{translation(30229)} ({response.status_code})")
                return
            return self.parse_response(response)
        except Exception as e:
            self.handle_exception(f"{translation(30229)}: {str(e)}")

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
            "title": item.get("title", ""),
            "type": "Torrent",
            "indexer": "Jackett",
            "publishDate": item.get("pubDate", ""),
            "provider": item.get("jackettindexer", {}).get("#text", ""),
            "guid": item.get("guid", ""),
            "downloadUrl": item.get("link", ""),
            "size": item.get("size", ""),
            "magnetUrl": attributes.get("magneturl", ""),
            "seeders": int(attributes.get("seeders", 0)),
            "peers": int(attributes.get("peers", 0)),
            "infoHash": attributes.get("infohash", ""),
        }
    )
