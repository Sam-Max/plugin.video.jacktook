from lib.clients.base import BaseClient
from lib.providers import burst_search, burst_search_episode, burst_search_movie
from lib.utils.kodi_utils import convert_size_to_bytes


class Burst(BaseClient):
    def __init__(self, notification):
        super().__init__("", notification)

    def search(self, tmdb_id, query, mode, media_type, season, episode):
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

    def parse_response(self, res):
        results = []
        for _, r in res:
            results.append(
                {
                    "title": r.title,
                    "type": "Torrent",
                    "indexer": "Burst",
                    "provider": r.indexer,
                    "guid": r.guid,
                    "info_hash": None,
                    "size": convert_size_to_bytes(r.size),
                    "seeders": int(r.seeders),
                    "peers": int(r.peers),
                }
            )
        return results
