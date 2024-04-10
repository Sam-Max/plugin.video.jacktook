import json
import requests
from lib.utils.kodi import get_prowlarr_timeout, notify, translation


class Prowlarr:
    def __init__(self, host, apikey, notification) -> None:
        self.host = host.rstrip("/")
        self.apikey = apikey
        self._notification = notification

    def search(
        self,
        query,
        mode,
        imdb_id,
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
            if mode == "tv":
                query = (
                    f"{query}{{Season:{int(season):02}}}{{Episode:{int(episode):02}}}"
                )
                url = f"{self.host}/api/v1/search?query={query}&categories=5000&type=tvsearch"
            elif mode == "movie":
                url = f"{self.host}/api/v1/search?query={query}&categories=2000"
            elif mode == "multi":
                url = f"{self.host}/api/v1/search?query={query}"
            if indexers:
                indexers_ids = indexers.split(",")
                indexers_ids = "".join(
                    [f"&indexerIds={index}" for index in indexers_ids]
                )
                url = url + indexers_ids
            res = requests.get(url, timeout=get_prowlarr_timeout(), headers=headers)
            if res.status_code != 200:
                notify(f"{translation(30230)} {res.status_code}")
                return
            res = json.loads(res.text)
            for r in res:
                r.update(
                    {
                        "quality_title": "",
                        "debridType": "",
                        "debridCached": False,
                        "debridPack": False,
                    }
                )
            return res
        except Exception as e:
            self._notification(f"{translation(30230)}: {str(e)}")


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
