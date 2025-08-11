from lib.clients.base import BaseClient
from lib.clients.base import TorrentStream

from lib.utils.kodi.utils import get_setting, notification, translation
from lib.utils.parsers import xmltodict
from lib.utils.kodi.settings import get_jackett_timeout

from typing import List, Optional, Callable, Any


class Jackett(BaseClient):
    def __init__(
        self, host: str, apikey: str, notification: Callable[[str], None]
    ) -> None:
        super().__init__(host, notification)
        self.apikey = apikey
        self.base_url = f"{self.host}/api/v2.0/indexers/all/results/torznab/api?apikey={self.apikey}"

    def _build_url(
        self,
        query: str,
        mode: str,
        season: Optional[int] = None,
        episode: Optional[int] = None,
        categories: Optional[List[int]] = None,
        additional_params: Optional[dict] = None,
    ) -> str:
        url = f"{self.base_url}&q={query}"
        if mode == "tv":
            url += "&t=tvsearch"
            if get_setting("include_season_packs"):
                url += f"&season={season}"
            else:
                url += f"&season={season}&ep={episode}"
        elif mode == "movies":
            url += "&t=movie"
        else:
            url += "&t=search"

        if categories:
            url += f"&cat={','.join(map(str, categories))}"

        if additional_params:
            for key, value in additional_params.items():
                url += f"&{key}={value}"

        return url

    def search(
        self,
        query: str,
        mode: str,
        season: Optional[int] = None,
        episode: Optional[int] = None,
        categories: Optional[List[int]] = None,
        additional_params: Optional[dict] = None,
    ) -> Optional[List[TorrentStream]]:
        try:
            url = self._build_url(
                query, mode, season, episode, categories, additional_params
            )
            response = self.session.get(url, timeout=get_jackett_timeout())
            if response.status_code != 200:
                notification(f"{translation(30229)} ({response.status_code})")
                return None
            return self.parse_response(response)
        except Exception as e:
            self.handle_exception(f"{translation(30229)}: {str(e)}")
            return None

    def parse_response(self, res: Any) -> Optional[List[TorrentStream]]:
        try:
            res_dict = xmltodict.parse(res.content)
            if res_dict:
                channel = res_dict.get("rss", {}).get("channel", {})
                items = channel.get("item")
                if not items:
                    return []
                results: List[TorrentStream] = []
                for item in items if isinstance(items, list) else [items]:
                    self.extract_result(results, item)
                return results
        except Exception as e:
            self.handle_exception(f"Error parsing Jackett response: {str(e)}")
            return None


    def extract_result(self, results: List[TorrentStream], item: dict) -> None:
        attrs = item.get("torznab:attr", [])
        if isinstance(attrs, dict):
            attrs = [attrs]
        attributes = {attr.get("@name"): attr.get("@value") for attr in attrs}
        results.append(
            TorrentStream(
                title=item.get("title", ""),
                type="Torrent",
                indexer="Jackett",
                publishDate=item.get("pubDate", ""),
                provider=item.get("jackettindexer", {}).get("#text", ""),
                guid=item.get("guid", ""),
                url=item.get("link", ""),
                size=item.get("size", ""),
                seeders=int(attributes.get("seeders", 0) or 0),
                peers=int(attributes.get("peers", 0) or 0),
                infoHash=str(attributes.get("infohash", "")),
                languages=[],
                fullLanguages="",
            )
        )
