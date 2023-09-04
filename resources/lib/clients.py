import json
import requests
from resources.lib.kodi import dialog_ok


class Jackett():
    def __init__(self, host, apikey) -> None:
        self.host = host
        self.apikey = apikey

    def search(self, query, tracker='', method='', insecure=False):
        try:
            if tracker == 'anime':
                url = f"{self.host}/api/v2.0/indexers/nyaasi/results?apikey={self.apikey}&Query={query}"
            else:
                if method == 'tv':
                    url = f"{self.host}/api/v2.0/indexers/all/results?apikey={self.apikey}&t=tvsearch&Query={query}"
                elif method == 'movie':
                    url = f"{self.host}/api/v2.0/indexers/all/results?apikey={self.apikey}&t=movie&Query={query}"
                else:
                    url = f"{self.host}/api/v2.0/indexers/all/results?apikey={self.apikey}&Query={query}"
            res = requests.get(url, verify=insecure)
            if res.status_code != 200:
                dialog_ok("jackewlarr", f"The request to Jackett failed. ({res.status_code})")
                return
            return json.loads(res.content)
        except Exception as e:
            dialog_ok("jackewlarr", f"The request to Jackett failed. {str(e)}")
            return

class Prowlarr():
    def __init__(self, host, apikey) -> None: 
        self.host = host
        self.apikey = apikey

    def search(self, query, tracker, indexers, anime_indexers, method, insecure=False):
        headers = {"Accept": "application/json",
                   "Content-Type": "application/json",
                   "X-Api-Key": self.apikey}
        try:
            if tracker == 'anime':
                if anime_indexers:
                    url = f"{self.host}/api/v1/search?query={query}&indexerIds={anime_indexers}"
                else:
                    dialog_ok("Prowlarr", f"You need to set Anime Indexer Ids for direct anime search")
                    return
            else:
                if method == 'tv':
                    url = f"{self.host}/api/v1/search?query={query}&Categories=5000"
                elif method == 'movie':
                    url = f"{self.host}/api/v1/search?query={query}&Categories=2000"
                else:
                    url = f"{self.host}/api/v1/search?query={query}"
                if indexers:
                    url = url + f"&indexerIds={indexers}" 
            res = requests.get(url, verify=insecure, headers=headers)
            if res.status_code != 200:
                dialog_ok("Prowlarr", f"The request to Prowlarr failed. ({res.status_code})")
                return
            return json.loads(res.text)
        except Exception as e:
            dialog_ok("Prowlarr", f"The request to Prowlarr failed. {str(e)}")
            return

