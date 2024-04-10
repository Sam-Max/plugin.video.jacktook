
from lib.providers import burst_search, burst_search_episode, burst_search_movie


class Burst:
    def __init__(self, notification) -> None:
        self._notification = notification

    def search(self, imdb_id, query, mode, media_type, season, episode):
        try:
            if mode == "tv" or media_type == "tv":
                results = burst_search_episode(imdb_id, query, season, episode)
            elif mode == "movie" or media_type == "movie":
                results = burst_search_movie(imdb_id, query)
            else:
                results = burst_search(query)
            if results:
                results = self.parse_response(results)
            return results
        except Exception as e:
            self._notification(f"Burst error: {str(e)}")

    def parse_response(self, res):
        results = []
        for p, r in res:
            results.append(
                {
                    "title":r.title,
                    "indexer": r.indexer,
                    "guid": r.guid,
                    "infoHash": r.guid,
                    "size": r.size,
                    "seeders": r.seeders,
                    "peers": r.peers,
                    "debridType": "",
                    "debridCached": False,
                    "debridPack": False,
                }
            )
        return results