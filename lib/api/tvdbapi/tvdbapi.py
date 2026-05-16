from datetime import timedelta

import requests

from lib.db.cached import cache
from lib.utils.kodi.settings import get_cache_expiration, is_cache_enabled


class TVDBAPI:
    def __init__(self):
        self.headers = {"User-Agent": "TheTVDB v.4 TV Scraper for Kodi"}
        self.apiKey = {"apikey": "edae60dc-1b44-4bac-8db7-65c0aaf5258b"}
        self.baseUrl = "https://api4.thetvdb.com/v4/"
        self.art = {}
        self.request_response = None
        self.threads = []

    def get_token(self):
        identifier = "tvdb_token"
        token = cache.get(identifier)
        if token:
            return token
        else:
            res = requests.post(self.baseUrl + "login", json=self.apiKey, headers=self.headers)
            data = res.json()
            token = data["data"].get("token")
            cache.set(
                identifier,
                token,
                timedelta(hours=get_cache_expiration() if is_cache_enabled() else 0),
            )
        return token

    def get_request(self, url):
        token = self.get_token()
        self.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/json"})
        url = self.baseUrl + url
        response = requests.get(url, headers=self.headers)
        if response:
            response = response.json().get("data")
            self.request_response = response
            return response
        else:
            return None

    def get_imdb_id(self, tvdb_id):
        imdb_id = None
        url = f"series/{tvdb_id}/extended"
        data = self.get_request(url)
        if data:
            imdb_id = [x.get("id") for x in data["remoteIds"] if x.get("type") == 2]
        return imdb_id[0] if imdb_id else None

    def get_seasons(self, tvdb_id):
        url = f"seasons/{tvdb_id}/extended"
        data = self.get_request(url)
        return data
