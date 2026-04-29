from ..clients.base import BaseClient, TorrentStream
from .providers import (
    burst_search,
    burst_search_episode,
    burst_search_movie,
    burst_search_season,
)
from ..utils.kodi.utils import convert_size_to_bytes, get_setting, kodilog
from typing import List, Optional, Dict, Any, Callable


class Burst(BaseClient):
    def __init__(self, notification: Callable) -> None:
        super().__init__("", notification)

    def search(
        self,
        tmdb_id: str,
        query: str,
        mode: str,
        media_type: str,
        season: Optional[int],
        episode: Optional[int],
        silent: bool = False,
    ) -> Optional[List[TorrentStream]]:
        try:
            if mode == "tv" or media_type == "tv":
                if get_setting("include_season_packs"):
                    results = burst_search_season(tmdb_id, query, season, silent=silent)
                else:
                    results = burst_search_episode(
                        tmdb_id, query, season, episode, silent=silent
                    )
            elif mode == "movies" or media_type == "movies":
                results = burst_search_movie(tmdb_id, query, silent=silent)
            else:
                results = burst_search(query, silent=silent)
            if results:
                results = self.parse_response(results)
            return results
        except Exception as e:
            self.handle_exception(f"Burst error: {str(e)}")

    def parse_response(self, res: List[Dict[str, Any]]) -> List[TorrentStream]:
        results = []
        for r in res:
            try:
                raw_seeders = getattr(r, "seeders", None)
                raw_peers = getattr(r, "peers", None)
                raw_size = getattr(r, "size", "")

                seeders = int(raw_seeders) if raw_seeders is not None else 0
                peers = int(raw_peers) if raw_peers is not None else 0
                size = convert_size_to_bytes(str(raw_size)) if raw_size is not None else 0

                results.append(
                    TorrentStream(
                        title=getattr(r, "title", ""),
                        type="Torrent",
                        indexer="Burst",
                        guid=getattr(r, "guid", ""),
                        infoHash="",
                        size=size,
                        seeders=seeders,
                        peers=peers,
                        languages=[],
                        fullLanguages="",
                        provider=getattr(r, "indexer", ""),
                        publishDate="",
                    )
                )
            except (ValueError, TypeError) as e:
                self.handle_exception(f"Burst parse error for result {getattr(r, 'title', '?')}: {e}")
                continue
        return results