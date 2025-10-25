from urllib.parse import quote
from typing import Any, Callable, List, Optional
import concurrent
import requests

from lib.clients.base import BaseClient
from lib.domain.torrent import TorrentStream
from lib.utils.general.utils import USER_AGENT_HEADER
from lib.utils.kodi.settings import get_jackett_timeout
from lib.utils.kodi.utils import get_setting, notification, translation
from lib.utils.parsers import xmltodict


class Jackett(BaseClient):
    def __init__(
        self, host: str, apikey: str, port: str, notification: Callable[[str], None]
    ) -> None:
        super().__init__(host, notification)
        self.apikey = apikey
        self.port = port
        self.host = host
        self.base_url = self._make_base_url("all")

    def _make_base_url(self, indexer_id: str) -> str:
        return f"{self.host}:{self.port}/api/v2.0/indexers/{indexer_id}/results/torznab/api?apikey={self.apikey}"

    def get_active_indexers(self) -> List[str]:
        url = f"{self.host}:{self.port}/api/v2.0/indexers?apikey={self.apikey}"
        try:
            headers = USER_AGENT_HEADER
            headers["Accept"] = "application/json"
            headers["Content-Type"] = "application/json"
            session = requests.Session()
            response = session.get(url, timeout=10, headers=headers)
            if "text/html" in response.headers.get("Content-Type", ""):
                response = session.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return [idx["id"] for idx in data if idx.get("configured")]
        except Exception as e:
            self.handle_exception(f"Error fetching Jackett indexers: {str(e)}")
        return []

    def _build_url(
        self,
        base_url: str,
        query: str,
        mode: str,
        season: Optional[int] = None,
        episode: Optional[int] = None,
        categories: Optional[List[int]] = None,
        additional_params: Optional[dict] = None,
        season_pack=False,
    ) -> str:
        url = f"{base_url}&q={quote(query)}"
        if mode == "tv":
            url += "&t=tvsearch"
            if season_pack:
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

    def search_indexer(
        self,
        base_url,
        query: str,
        mode: str,
        season: Optional[int] = None,
        episode: Optional[int] = None,
        categories: Optional[List[int]] = None,
        additional_params: Optional[dict] = None,
    ) -> Optional[List[TorrentStream]]:
        try:
            results = []
            futures = []
            with concurrent.futures.ThreadPoolExecutor() as executor:
                if mode == "tv" and season:
                    if episode:
                        url_ep = self._build_url(
                            base_url,
                            query,
                            mode,
                            season,
                            episode,
                            categories,
                            additional_params,
                        )
                        futures.append(
                            executor.submit(
                                self.session.get, url_ep, timeout=get_jackett_timeout()
                            )
                        )
                    if get_setting("include_season_packs"):
                        url_season = self._build_url(
                            base_url,
                            query,
                            mode,
                            season,
                            None,
                            categories,
                            additional_params,
                            season_pack=True,
                        )
                        futures.append(
                            executor.submit(
                                self.session.get,
                                url_season,
                                timeout=get_jackett_timeout(),
                            )
                        )
                else:
                    url = self._build_url(
                        base_url,
                        query,
                        mode,
                        season,
                        episode,
                        categories,
                        additional_params,
                    )
                    futures.append(
                        executor.submit(
                            self.session.get, url, timeout=get_jackett_timeout()
                        )
                    )

            for future in concurrent.futures.as_completed(futures):
                response = future.result()
                if response.status_code == 200:
                    res = self.parse_response(response)
                    if res:
                        results.extend(res)
                else:
                    notification(f"{translation(30229)} ({response.status_code})")
            return results if results else None
        except Exception as e:
            self.handle_exception(f"{translation(30229)}: {str(e)}")
            return None

    def search(
        self,
        query: str,
        mode: str,
        season: Optional[int] = None,
        episode: Optional[int] = None,
        categories: Optional[List[int]] = None,
        additional_params: Optional[dict] = None,
    ) -> Optional[List[TorrentStream]]:
        """Search all active indexers in parallel and combine results."""
        all_results = []
        indexers = self.get_active_indexers()
        futures = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for idx in indexers:
                base_url = self._make_base_url(idx)
                futures.append(
                    executor.submit(
                        self.search_indexer,
                        base_url,
                        query,
                        mode,
                        season,
                        episode,
                        categories,
                        additional_params,
                    )
                )
            for future in concurrent.futures.as_completed(futures):
                results = future.result()
                if results:
                    all_results.extend(results)
        return all_results if all_results else None

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
