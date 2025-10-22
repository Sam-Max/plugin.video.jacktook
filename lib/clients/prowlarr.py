from lib.clients.base import BaseClient, TorrentStream
from lib.utils.kodi.utils import get_setting, notification, translation
from lib.utils.kodi.settings import get_prowlarr_timeout

from typing import Dict, List, Optional, Any, Callable


class Prowlarr(BaseClient):
    def __init__(self, host: str, port: str, apikey: str, notification: Callable) -> None:
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
    ) -> Optional[List[TorrentStream]]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Api-Key": self.apikey,
        }
        try:
            params: Dict[str, Any] = {"query": query, "type": "search"}
            if mode == "tv":
                params["categories"] = [5000, 8000]
                if get_setting("include_season_packs"):
                    params["query"] = f"{query} S{int(season):02d}"
                else:
                    params["query"] = f"{query} S{int(season):02d}E{int(episode):02d}"
            elif mode == "movies":
                params["categories"] = [2000, 8000]
            elif mode == "anime":
                params["categories"] = [2000, 5070, 5000, 127720, 140679]
            if indexers:
                # Accept comma or space separated
                indexer_ids = [
                    i.strip() for i in indexers.replace(",", " ").split() if i.strip()
                ]
                if indexer_ids:
                    params["indexerIds"] = indexer_ids
            response = self.session.get(
                self.base_url,
                params=params,
                timeout=get_prowlarr_timeout(),
                headers=headers,
            )
            if response.status_code != 200:
                notification(f"{translation(30230)} {response.status_code}")
                return None
            return self.parse_response(response)
        except Exception as e:
            self.handle_exception(f"{translation(30230)}: {str(e)}")
            return None

    def parse_response(self, res: Any) -> List[TorrentStream]:
        response = res.json()
        results = []
        for res in response:
            results.append(
                TorrentStream(
                    title=res.get("title", ""),
                    type="Torrent",
                    indexer="Prowlarr",
                    provider=res.get("indexer"),
                    peers=int(res.get("peers", 0)),
                    seeders=int(res.get("seeders", 0)),
                    guid=res.get("guid", ""),
                    infoHash=res.get("infoHash", ""),
                    size=int(res.get("size", 0)),
                    languages=res.get("languages", []),
                    fullLanguages=res.get("fullLanguages", ""),
                    publishDate=res.get("publishDate", ""),
                )
            )
        return results
