from lib.clients.base import BaseClient, TorrentStream
from lib.clients.burst.providers import (
    burst_search,
    burst_search_episode,
    burst_search_movie,
)
from lib.utils.kodi.utils import convert_size_to_bytes
from typing import List, Optional, Dict, Any


class Burst(BaseClient):
    def __init__(self, notification: callable) -> None:
        super().__init__("", notification)

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
            if mode == "tv" or media_type == "tv":
                results = burst_search_episode(tmdb_id, query, season, episode)
            elif mode == "movies" or media_type == "movies":
                results = burst_search_movie(tmdb_id, query)
            else:
                results = burst_search(query)
            if results:
                results = self.parse_response(results)
            return results
        except Exception as e:
            self.handle_exception(f"Burst error: {str(e)}")

    def parse_response(self, res: List[Dict[str, Any]]) -> List[TorrentStream]:
        results = []
        for _, r in res:
            results.append(
                TorrentStream(
                    title=r.title,
                    type="Torrent",
                    indexer="Burst",
                    guid=r.guid,
                    infoHash="",
                    size=convert_size_to_bytes(r.size),
                    seeders=int(r.seeders),
                    peers=int(r.peers),
                    languages=[],
                    fullLanguages="",
                    provider=r.indexer,
                    publishDate="",
                )
            )
        return results
