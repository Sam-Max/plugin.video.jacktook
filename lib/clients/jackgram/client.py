from typing import List, Dict, Optional, Any
from lib.clients.base import BaseClient, TorrentStream
from lib.utils.kodi.utils import kodilog, translation


class Jackgram(BaseClient):
    def __init__(self, host: str, notification: callable) -> None:
        super().__init__(host, notification)

    def search(
        self,
        tmdb_id: str,
        query: str,
        mode: str,
        media_type: str,
        season: Optional[int],
        episode: Optional[int],
    ) -> Optional[List[TorrentStream]]:
        try:
            kodilog(f"Searching for {query} on Jackgram")

            if mode == "tv" or media_type == "tv":
                url = f"{self.host}/stream/series/{tmdb_id}:{season}:{episode}.json"
            elif mode == "movies" or media_type == "movies":
                url = f"{self.host}/stream/movie/{tmdb_id}.json"
            else:
                url = f"{self.host}/search?query={query}"

            kodilog(f"URL: {url}")

            res = self.session.get(url, timeout=10)
            if res.status_code != 200:
                return
            
            if mode in ["tv", "movies"]:
                return self.parse_response(res)
            else:
                return self.parse_response_search(res)
        except Exception as e:
            self.handle_exception(f"{translation(30232)}: {e}")

    def get_latest(self, page: int) -> Optional[Dict[str, Any]]:
        url = f"{self.host}/stream/latest?page={page}"
        res = self.session.get(url, timeout=10)
        if res.status_code != 200:
            return
        return res.json()

    def get_files(self, page: int) -> Optional[Dict[str, Any]]:
        url = f"{self.host}/stream/files?page={page}"
        res = self.session.get(url, timeout=10)
        if res.status_code != 200:
            return
        return res.json()

    def parse_response(self, res: Any) -> List[TorrentStream]:
        res = res.json()
        results = []
        for item in res["streams"]:
            results.append(
                TorrentStream(
                    title=item["title"],
                    type="Direct",
                    indexer=item["name"],
                    size=item["size"],
                    publishDate=item["date"],
                    url=item["url"],
                )
            )
        return results

    def parse_response_search(self, res: Any) -> List[TorrentStream]:
        res = res.json()
        results = []
        for item in res["results"]:
            if item.get("type") == "file":
                file_info = self._extract_file_info(item)
                results.append(TorrentStream(**file_info))
            else:
                for file in item.get("files", []):
                    file_info = self._extract_file_info(file)
                    results.append(TorrentStream(**file_info))
        return results

    def _extract_file_info(self, file):
        return {
            "title": file.get("title", ""),
            "type": "Direct",
            "indexer": file.get("name", ""),
            "size": file.get("size", ""),
            "publishDate": file.get("date", ""),
            "url": file.get("url", ""),
        }
