from lib.clients.base import BaseClient
from lib.utils.kodi_utils import translation
from lib.utils.settings import get_prowlarr_timeout


class Prowlarr(BaseClient):
    def __init__(self, host, apikey, notification):
        super().__init__(host, notification)
        self.base_url = f"{self.host}/api/v1/search"
        self.apikey = apikey

    def search(
        self,
        query,
        mode,
        season,
        episode,
        indexers,
    ):
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Api-Key": self.apikey,
        }

        try:
            params = {"query": query}
            params["type"] = "search"
            
            if mode == "tv":
                params["categories"] = [5000, 8000]
                query = f"{query} S{int(season):02d}E{int(episode):02d}"
                params["query"] = query
            elif mode == "movies":
                params["categories"] = [2000, 8000]

            if indexers:
                for indexer_id in indexers.split():
                    params[f"indexerIds"] = indexer_id

            response = self.session.get(
                self.base_url,
                params=params,
                timeout=get_prowlarr_timeout(),
                headers=headers,
            )
            if response.status_code != 200:
                self.notification(f"{translation(30230)} {response.status_code}")
                return
            return self.parse_response(response)
        except Exception as e:
            self.handle_exception(f"{translation(30230)}: {str(e)}")

    def parse_response(self, res):
        response = res.json()
        for res in response:
            res.update(
                {
                    "type": "Torrent",
                    "indexer": "Prowlarr",
                    "provider": res.get("indexer"),
                    "peers": int(res.get("peers", 0)),
                    "seeders": int(res.get("seeders", 0)),
                }
            )
        return response


""" if anime_indexers:
    anime_categories = [2000, 5070, 5000, 127720, 140679]
    anime_categories_id = "".join(
        [f"&categories={cat}" for cat in anime_categories]
    )
    anime_indexers_id = anime_indexers.split(",")
    anime_indexers_id = "".join(
        [f"&indexerIds={index}" for index in anime_indexers_id]
    )
    url = f"{self.host}/api/v1/search?query={query}{anime_categories_id}{anime_indexers_id}" """
