from typing import Any, Callable, Dict, List, Optional
from urllib.parse import quote

from lib.clients.base import BaseClient, TorrentStream
from lib.utils.kodi.utils import kodilog, translation


def _sanitize_url_for_log(url: str) -> str:
    if "|Authorization=Bearer" in url:
        idx = url.find("|Authorization=Bearer")
        return url[:idx] + "|Authorization=Bearer ***"
    return url


class Jackgram(BaseClient):
    def __init__(self, host: str, notification: Callable, token: Optional[str] = None) -> None:
        super().__init__(host, notification)
        self.token = token
        if token:
            self.session.headers.update({"Authorization": f"Bearer {token}"})

    def search(
        self,
        tmdb_id: str,
        query: str,
        mode: str,
        media_type: str,
        season: Optional[int],
        episode: Optional[int],
        **kwargs: Any,
    ) -> List[TorrentStream]:
        try:
            if mode == "tv" or media_type == "tv":
                if tmdb_id and season is not None and episode is not None:
                    url = f"{self.host}/stream/series/{tmdb_id}:{season}:{episode}.json"
                else:
                    url = f"{self.host}/search?query={quote(query or '', safe='')}&page=1"
            elif mode == "movies" or media_type == "movies":
                if tmdb_id:
                    url = f"{self.host}/stream/movie/{tmdb_id}.json"
                else:
                    url = f"{self.host}/search?query={quote(query or '', safe='')}&page=1"
            else:
                url = f"{self.host}/search?query={quote(query or '', safe='')}&page=1"

            kodilog(f"Jackgram search URL: {_sanitize_url_for_log(url)}")

            res = self.session.get(url, timeout=10)
            if res.status_code != 200:
                kodilog(
                    f"Jackgram search failed with status {res.status_code} "
                    f"for URL: {_sanitize_url_for_log(url)}"
                )
                return []

            if mode in ["tv", "movies"]:
                return self.parse_response(res)
            else:
                return self.parse_response_search(res)
        except Exception as e:
            self.handle_exception(f"{translation(30232)}: {e}")
            return []

    def get_latest_movies(self, page: int) -> Optional[Dict[str, Any]]:
        try:
            url = f"{self.host}/stream/movies/latest?page={page}"
            res = self.session.get(url, timeout=10)
            if res.status_code != 200:
                kodilog(f"get_latest_movies failed with status {res.status_code}")
                return
            return res.json()
        except Exception as e:
            self.handle_exception(f"{translation(30232)}: {e}")

    def get_latest_series(self, page: int) -> Optional[Dict[str, Any]]:
        try:
            url = f"{self.host}/stream/series/latest?page={page}"
            res = self.session.get(url, timeout=10)
            if res.status_code != 200:
                kodilog(f"get_latest_series failed with status {res.status_code}")
                return
            return res.json()
        except Exception as e:
            self.handle_exception(f"{translation(30232)}: {e}")

    def get_files(self, page: int) -> Optional[Dict[str, Any]]:
        try:
            url = f"{self.host}/stream/files?page={page}"
            res = self.session.get(url, timeout=10)
            if res.status_code != 200:
                kodilog(f"get_files failed with status {res.status_code}")
                return
            return res.json()
        except Exception as e:
            self.handle_exception(f"{translation(30232)}: {e}")

    def parse_response(self, res: Any) -> List[TorrentStream]:
        data = res.json() if hasattr(res, "json") else res
        streams = data.get("streams", []) if isinstance(data, dict) else []
        if not isinstance(streams, list):
            return []
        results = []
        for item in streams:
            if not isinstance(item, dict):
                continue
            url = item.get("url", "")

            results.append(
                TorrentStream(
                    title=item.get("title", ""),
                    type="Direct",
                    indexer=item.get("name", ""),
                    size=item.get("size", ""),
                    publishDate=item.get("date", ""),
                    url=url,
                    guid=item.get("guid", ""),
                    infoHash=item.get("infoHash", ""),
                    seeders=item.get("seeders", 0),
                    languages=item.get("languages", []),
                    fullLanguages=item.get("fullLanguages", ""),
                    provider=item.get("provider", ""),
                    peers=item.get("peers", 0),
                )
            )
        return results

    def parse_response_search(self, res: Any) -> List[TorrentStream]:
        data = res.json() if hasattr(res, "json") else res
        results_data = data.get("results", []) if isinstance(data, dict) else []
        if not isinstance(results_data, list):
            return []
        results = []
        for item in results_data:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "file":
                file_info = self._extract_file_info(item)
                results.append(TorrentStream(**file_info))
            else:
                files = item.get("files", [])
                if not isinstance(files, list):
                    continue
                for file in files:
                    file_info = self._extract_file_info(file)
                    results.append(TorrentStream(**file_info))
        return results

    def _extract_file_info(self, file):
        if not isinstance(file, dict):
            return {
                "title": "",
                "type": "Direct",
                "indexer": "",
                "size": "",
                "publishDate": "",
                "url": "",
            }
        url = file.get("url", "")

        return {
            "title": file.get("title", ""),
            "type": "Direct",
            "indexer": file.get("name", ""),
            "size": file.get("size", ""),
            "publishDate": file.get("date", ""),
            "url": url,
        }
