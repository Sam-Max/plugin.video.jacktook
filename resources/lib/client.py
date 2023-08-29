from datetime import datetime
import json
import requests
from resources.lib.util import dialog_ok


class Jackett():
    def __init__(self, db, url, apikey) -> None:
        self.db = db
        self.jackett_apikey = apikey
        self.jackett_url = url

    def set_watched(self, title, magnet, url):
        if title not in self.db.database["jt:watch"]:
            self.db.database["jt:watch"][title] = True

        self.db.database["jt:history"][title] = {
            "timestamp": datetime.now(),
            "url": url,
            "magnet": magnet
        }
        self.db.commit()

    def is_torrent_watched(self, title):
        return self.db.database["jt:watch"].get(title, False)

    def search(self, query, tracker='', mode='', insecure=False):
        try:
            if tracker == 'nyaa':
                url = f"{self.jackett_url}/api/v2.0/indexers/nyaasi/results?apikey={self.jackett_apikey}&Query={query}"
            else:
                if mode == 'tv':
                    url = f"{self.jackett_url}/api/v2.0/indexers/all/results?apikey={self.jackett_apikey}&t=tvsearch&Query={query}"
                elif mode == 'movie':
                    url = f"{self.jackett_url}/api/v2.0/indexers/all/results?apikey={self.jackett_apikey}&t=movie&Query={query}"
                else:
                    url = f"{self.jackett_url}/api/v2.0/indexers/all/results?apikey={self.jackett_apikey}&Query={query}"
            res = requests.get(url, verify=insecure)
            if res.status_code != 200:
                dialog_ok("jacktorr", f"The request to Jackett failed. ({res.status_code})")
                return None
            res_dict = json.loads(res.content)
            return res_dict
        except Exception as e:
            dialog_ok("jacktorr", f"The request to Jackett failed. {str(e)}")
            return None

        
