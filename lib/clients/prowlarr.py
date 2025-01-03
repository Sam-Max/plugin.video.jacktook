import requests
from lib.api.jacktook.kodi import kodilog
from lib.utils.kodi_utils import notification, translation
from lib.utils.settings import get_prowlarr_timeout


class Prowlarr:
    def __init__(self, host, apikey, notification) -> None:
        self.host = host.rstrip("/")
        self.base_url = f"{self.host}/api/v1/search"
        self.apikey = apikey
        self._notification = notification

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

        params = {"query": query}

        try:
            if mode == "tv":
                params["categories"] = [5000, 8000]
                params["type"] = "search"
                query = f"{query} S{int(season):02d}E{int(episode):02d}"
                params["query"] = query
            elif mode == "movies":
                params["categories"] = [2000, 8000]
                params["type"] = "search"
            elif mode == "multi":
                params["type"] = "search"

            if indexers:
                for indexer_id in indexers.split():
                    params[f"indexerIds"] = indexer_id

            response = requests.get(
                self.base_url,
                params=params,
                timeout=get_prowlarr_timeout(),
                headers=headers,
            )
            if response.status_code != 200:
                notification(f"{translation(30230)} {response.status_code}")
                return
            return self.parse_response(response)
        except Exception as e:
            self._notification(f"{translation(30230)}: {str(e)}")

    def parse_response(self, res):
        response = res.json()
        for res in response:
            res.update(
                {
                    "type": "Torrent",
                    "provider": "Prowlarr",
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
