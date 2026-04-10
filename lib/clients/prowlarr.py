from lib.clients.base import BaseClient, TorrentStream
from lib.jacktook.utils import kodilog
from lib.utils.kodi.logging import summarize_locator_for_log
from lib.utils.kodi.utils import get_setting, notification, translation
from lib.utils.kodi.settings import get_prowlarr_timeout

from typing import Dict, List, Optional, Any, Callable
import concurrent.futures


class Prowlarr(BaseClient):
    def __init__(
        self, host: str, apikey: str, port: str, notification: Callable
    ) -> None:
        super().__init__(host, notification)
        self.base_url = f"{self.host}:{port}/api/v1/search"
        self.apikey = apikey

    def search(
        self,
        query: str,
        mode: str,
        season: Optional[int] = None,
        episode: Optional[int] = None,
        indexers: Optional[str] = None,
        variant=None,
        year: Optional[int] = None,
    ) -> Optional[List[TorrentStream]]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Api-Key": self.apikey,
        }
        try:
            season = self._coerce_int(season)
            episode = self._coerce_int(episode)
            results = []
            futures = []

            if mode == "movies" and year:
                query_with_year = f"{query} {year}"
            else:
                query_with_year = query

            with concurrent.futures.ThreadPoolExecutor() as executor:
                if mode == "tv" and season:
                    if episode:
                        params_ep: Dict[str, Any] = {
                            "query": f"{query} S{season:02d}E{episode:02d}",
                            "type": "search",
                            "categories": [5000, 8000],
                        }
                        if indexers:
                            indexer_ids = [
                                i.strip()
                                for i in indexers.replace(",", " ").split()
                                if i.strip()
                            ]
                            if indexer_ids:
                                params_ep["indexerIds"] = indexer_ids
                        futures.append(
                            executor.submit(
                                self.session.get,
                                self.base_url,
                                params=params_ep,
                                timeout=get_prowlarr_timeout(),
                                headers=headers,
                            )
                        )
                    # Season pack query
                    if get_setting("include_season_packs"):
                        params_season: Dict[str, Any] = {
                            "query": f"{query} S{season:02d}",
                            "type": "search",
                            "categories": [5000, 8000],
                        }
                        if indexers:
                            indexer_ids = [
                                i.strip()
                                for i in indexers.replace(",", " ").split()
                                if i.strip()
                            ]
                            if indexer_ids:
                                params_season["indexerIds"] = indexer_ids
                        futures.append(
                            executor.submit(
                                self.session.get,
                                self.base_url,
                                params=params_season,
                                timeout=get_prowlarr_timeout(),
                                headers=headers,
                            )
                        )
                else:
                    params: Dict[str, Any] = {
                        "query": query_with_year,
                        "type": "search",
                    }
                    if mode == "movies":
                        params["categories"] = [2000, 8000]
                    elif mode == "anime":
                        params["categories"] = [2000, 5070, 5000, 127720, 140679]
                    if indexers:
                        indexer_ids = [
                            i.strip()
                            for i in indexers.replace(",", " ").split()
                            if i.strip()
                        ]
                        if indexer_ids:
                            params["indexerIds"] = indexer_ids
                    futures.append(
                        executor.submit(
                            self.session.get,
                            self.base_url,
                            params=params,
                            timeout=get_prowlarr_timeout(),
                            headers=headers,
                        )
                    )

                for future in concurrent.futures.as_completed(futures):
                    response = future.result()
                    if response.status_code != 200:
                        notification(f"{translation(30230)} {response.status_code}")
                    else:
                        res = self.parse_response(response)
                        if res:
                            results.extend(res)
            return results if results else None
        except Exception as e:
            self.handle_exception(f"{translation(30230)}: {str(e)}")
            return None

    @staticmethod
    def _coerce_int(value: Any) -> Optional[int]:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def parse_response(self, res: Any) -> List[TorrentStream]:
        response = res.json()
        results = []
        for res in response:
            title = res.get("title", "")
            provider = res.get("indexer")
            guid = res.get("guid", "")
            download_url = res.get("downloadUrl", "")
            magnet_url = res.get("magnetUrl", "")
            info_url = res.get("infoUrl", "")
            info_hash = res.get("infoHash", "")

            kodilog(
                "Prowlarr parsed result: title={!r}, provider={!r}, guid={!r}, download={!r}, magnet={!r}, info={!r}, infohash={!r}, has_magnet={}, has_http_url={}, has_infohash={}".format(
                    title,
                    provider,
                    summarize_locator_for_log(guid),
                    summarize_locator_for_log(download_url),
                    summarize_locator_for_log(magnet_url),
                    summarize_locator_for_log(info_url),
                    str(info_hash).lower()[:12],
                    bool(
                        str(magnet_url).startswith("magnet:?")
                        or str(download_url).startswith("magnet:?")
                        or str(guid).startswith("magnet:?")
                    ),
                    bool(
                        str(download_url).startswith(("http://", "https://"))
                        or str(info_url).startswith(("http://", "https://"))
                        or str(guid).startswith(("http://", "https://"))
                    ),
                    bool(info_hash),
                )
            )

            results.append(
                TorrentStream(
                    title=title,
                    type="Torrent",
                    indexer="Prowlarr",
                    provider=provider,
                    peers=int(res.get("peers", 0)),
                    seeders=int(res.get("seeders", 0)),
                    guid=guid,
                    infoHash=info_hash,
                    size=int(res.get("size", 0)),
                    languages=res.get("languages", []),
                    fullLanguages=res.get("fullLanguages", ""),
                    publishDate=res.get("publishDate", ""),
                    url=download_url,
                )
            )
        return results
