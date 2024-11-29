import requests
from lib.api.jacktook.kodi import kodilog


class AniZipApi:
    base_url = "https://api.ani.zip/"

    def mapping(self, anilist_id):
        params = {"anilist_id": anilist_id}
        res = self.make_request(url="mappings", params=params)
        if res:
            return res["mappings"]
        
    def episodes(self, anilist_id):
        params = {"anilist_id": anilist_id}
        res = self.make_request(url="mappings", params=params)
        if res:
            return res["episodes"]

    def make_request(self, url, params):
        res = requests.get(
            self.base_url + url,
            params=params,
        )
        if res.status_code == 200:
            return res.json()
        else:
            kodilog(f"Error::{res.text}")
