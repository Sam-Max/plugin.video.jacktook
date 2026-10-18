import concurrent
import time
from typing import Any, List, Optional
from urllib.parse import quote, urlparse

import requests

from lib.clients.base import BaseClient
from lib.domain.torrent import TorrentStream
from lib.jacktook.utils import kodilog
from lib.utils.general.utils import USER_AGENT_HEADER
from lib.utils.kodi.logging import summarize_locator_for_log
from lib.utils.kodi.settings import get_jackett_timeout
from lib.utils.kodi.utils import get_setting, notification, translation
from lib.utils.parsers import xmltodict

RATE_LIMIT_RETRIES = 3
RATE_LIMIT_BACKOFF = 1.0


def _xml_text(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("#text", "")
    return str(value or "")


class Jackett(BaseClient):
    def __init__(
        self,
        host: str,
        apikey: str,
        port: str,
        notification,
        session: Optional[requests.Session] = None,
    ) -> None:
        super().__init__(host, notification)
        self.apikey = apikey
        self.port = port
        self.host = host
        self.base_url = self._make_base_url("all")
        self.session = session or requests.Session()
        self.session.headers.update(USER_AGENT_HEADER.copy())

    def _make_base_url(self, indexer_id: str) -> str:
        host = self.host.strip().rstrip("/")
        # Public instances (e.g. https://jac.red) are served without a port;
        # skip it when empty or when the host already carries one.
        port = str(self.port or "").strip()
        if port and urlparse(host).port is None:
            host = f"{host}:{port}"
        return f"{host}/api/v2.0/indexers/{indexer_id}/results/torznab/api?apikey={self.apikey or ''}"

    def _get(self, url: str) -> requests.Response:
        # Public Jackett-compatible instances rate limit parallel requests (HTTP 429).
        response = self.session.get(url, timeout=get_jackett_timeout())
        for attempt in range(RATE_LIMIT_RETRIES):
            if response.status_code != 429:
                break
            time.sleep(RATE_LIMIT_BACKOFF * (attempt + 1))
            response = self.session.get(url, timeout=get_jackett_timeout())
        return response

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
        year: Optional[int] = None,
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

        if year and mode == "movies":
            url += f"&year={year}"

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
        year: Optional[int] = None,
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
                            year=year,
                        )
                        futures.append(
                            executor.submit(self._get, url_ep)
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
                            year=year,
                        )
                        futures.append(
                            executor.submit(self._get, url_season)
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
                        year=year,
                    )
                    futures.append(
                        executor.submit(self._get, url)
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
            self.handle_exception(f"{translation(30229)}: {e!s}")
            return None

    def search(
        self,
        query: str,
        mode: str,
        season: Optional[int] = None,
        episode: Optional[int] = None,
        categories: Optional[List[int]] = None,
        additional_params: Optional[dict] = None,
        variant=None,
        year: Optional[int] = None,
    ) -> Optional[List[TorrentStream]]:
        try:
            return self.search_indexer(
                self.base_url,
                query,
                mode,
                season,
                episode,
                categories,
                additional_params,
                year=year,
            )
        except Exception as e:
            self.handle_exception(f"{translation(30229)}: {e!s}")
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
                kodilog(f"Parsed {len(results)} results from Jackett")
                return results
        except Exception as e:
            self.handle_exception(f"Error parsing Jackett response: {e!s}")
            return None

    def extract_result(self, results: List[TorrentStream], item: dict) -> None:
        attrs = item.get("torznab:attr", [])
        if isinstance(attrs, dict):
            attrs = [attrs]
        attributes = {attr.get("@name"): attr.get("@value") for attr in attrs}
        enclosure = item.get("enclosure", {})
        if not isinstance(enclosure, dict):
            enclosure = {}
        link = _xml_text(item.get("link", ""))
        # <guid isPermaLink="false"> (e.g. jac.red) is parsed into a dict by xmltodict.
        guid = _xml_text(item.get("guid", ""))
        info_hash = str(attributes.get("infohash", ""))
        enclosure_url = enclosure.get("@url", "")
        provider = item.get("jackettindexer", {}).get("#text", "")

        kodilog(
            "Jackett parsed result: title={!r}, provider={!r}, guid={!r}, link={!r}, enclosure={!r}, infohash={!r}, has_magnet={}, has_http_url={}, has_infohash={}".format(
                item.get("title", ""),
                provider,
                summarize_locator_for_log(guid),
                summarize_locator_for_log(link),
                summarize_locator_for_log(enclosure_url),
                info_hash[:12].lower(),
                bool(str(link).startswith("magnet:?") or str(guid).startswith("magnet:?")),
                bool(
                    str(link).startswith(("http://", "https://"))
                    or str(guid).startswith(("http://", "https://"))
                    or str(enclosure_url).startswith(("http://", "https://"))
                ),
                bool(info_hash),
            )
        )

        results.append(
            TorrentStream(
                title=item.get("title", ""),
                type="Torrent",
                indexer="Jackett",
                publishDate=item.get("pubDate", ""),
                provider=provider,
                guid=guid,
                url=link,
                size=item.get("size", ""),
                seeders=int(attributes.get("seeders", 0) or 0),
                peers=int(attributes.get("peers", 0) or 0),
                infoHash=info_hash,
                languages=[],
                fullLanguages="",
            )
        )
