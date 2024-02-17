import json
import requests


class FindMyAnime:
    base_url = "https://find-my-anime.dtimur.de/api"

    def get_anime_data(self, anime_id, anime_id_provider):
        params = {"id": anime_id, "provider": anime_id_provider, "includeAdult": "true"}
        _, res = self.make_request(params=params)
        return res

    def make_request(self, params):
        res = requests.get(
            self.base_url,
            params=params,
        )
        if res.status_code == 200:
            return res.status_code, json.loads(res.text)
        else:
            error_message = f"Simkl Error::{res.text}"
            return error_message, {}
