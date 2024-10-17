import json
import requests
from datetime import timedelta
from lib.db.cached import cache
from lib.utils.settings import is_cache_enabled, get_cache_expiration

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
        token = cache.get(identifier, hashed_key=True)
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
                hashed_key=True,
            )
        return token

    def get_request(self, url):
        token = self.get_token()
        self.headers.update(
            {
                "Authorization": "Bearer {0}".format(token),
                "Accept": "application/json"
            }
        )
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
        url = "series/{}/extended".format(tvdb_id)
        data = self.get_request(url)
        if data:
            imdb_id = [x.get("id") for x in data["remoteIds"] if x.get("type") == 2]
        return imdb_id[0] if imdb_id else None

    def get_seasons(self, tvdb_id):
        url = "seasons/{}/extended".format(tvdb_id)
        data = self.get_request(url)
        return data
