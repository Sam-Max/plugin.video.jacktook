import json
from urllib.parse import quote
import requests
from resources.lib.kodi import Keyboard, get_setting, notify, translation
from resources.lib.utils import Indexer
from urllib3.exceptions import InsecureRequestWarning



def get_client():
    indexer = get_setting("indexer")

    if indexer == Indexer.JACKETT:
        host = get_setting("jackett_host")
        host = host.rstrip("/")
        api_key = get_setting("jackett_apikey")

        if not host or not api_key:
            notify(translation(30220))
            return

        if len(api_key) != 32:
            notify(translation(30221))
            return

        return Jackett(host, api_key)

    elif indexer == Indexer.PROWLARR:
        host = get_setting("prowlarr_host")
        host = host.rstrip("/")
        api_key = get_setting("prowlarr_apikey")

        if not host or not api_key:
            notify(translation(30223))
            return

        if len(api_key) != 32:
            notify(translation(30224))
            return

        return Prowlarr(host, api_key)


class Jackett:
    def __init__(self, host, apikey) -> None:
        self.host = host
        self.apikey = apikey

    def search(self, query, mode, insecure=False):
        try:
            if mode == "tv":
                url = f"{self.host}/api/v2.0/indexers/all/results?apikey={self.apikey}&t=tvsearch&Query={query}"
            elif mode == "movie":
                url = f"{self.host}/api/v2.0/indexers/all/results?apikey={self.apikey}&t=movie&Query={query}"
            elif mode == "anime":
                url = f"{self.host}/api/v2.0/indexers/nyaasi/results?apikey={self.apikey}&t=search&Query={query}"
            elif mode == "multi":
                url = f"{self.host}/api/v2.0/indexers/all/results?apikey={self.apikey}&t=search&Query={query}"
            res = requests.get(url, verify=insecure)
            if res.status_code != 200:
                notify(f"{translation(30229)} ({res.status_code})")
                return
            return self._parse_response(res)
        except Exception as e:
            notify(f"{translation(30229)} {str(e)}")
            return

    def _parse_response(self, response):
        results = []
        res_dict = json.loads(response.content)
        for res in res_dict["Results"]:
            model = {
                "title": res["Title"],
                "indexer": res["Tracker"],
                "publishDate": res["PublishDate"],
                "guid": res["Guid"],
                "magnetUrl": res["MagnetUri"],
                "downloadUrl": res["Link"],
                "size": res["Size"],
                "seeders": res["Seeders"],
                "peers": res["Peers"],
                "infoHash": res["InfoHash"],
                "rdCached": False,
                "rdLinks": [],
            }
            results.append(model)
        return results


class Prowlarr:
    def __init__(self, host, apikey) -> None:
        self.host = host
        self.apikey = apikey

    def search(self, query, indexers, anime_indexers, mode, insecure=False):
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Api-Key": self.apikey,
        }
        try:
            if mode == "tv":
                url = f"{self.host}/api/v1/search?query={query}&Categories=5000"
            elif mode == "movie":
                url = f"{self.host}/api/v1/search?query={query}&Categories=2000"
            elif mode == "anime":
                if anime_indexers:
                    anime_indexers_url = "".join(
                        [f"&IndexerIds={index}" for index in anime_indexers]
                    )
                    url = f"{self.host}/api/v1/search?query={query}{anime_indexers_url}"
                else:
                    notify(translation(30231))
                    return
            elif mode == "multi":
                url = f"{self.host}/api/v1/search?query={query}"
            if indexers:
                indexers_url = "".join([f"&IndexerIds={index}" for index in indexers])
                url = url + indexers_url
            res = requests.get(url, verify=insecure, headers=headers)
            if res.status_code != 200:
                notify(f"{translation(30230)} {res.status_code}")
                return
            return json.loads(res.text)
        except Exception as e:
            notify(f"{translation(30230)} {str(e)}")
            return


def search_api(query, mode, dialog):
    query = None if query == "None" else query

    indexer = get_setting("indexer")
    jackett_insecured = get_setting("jackett_insecured")
    prowlarr_insecured = get_setting("prowlarr_insecured")

    if prowlarr_insecured or jackett_insecured:
        requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

    if indexer == Indexer.JACKETT:
        jackett = get_client()
        if not jackett:
            return None, None

        if not query:
            text = Keyboard(id=30243)
            if text:
                query = quote(text)
                dialog.create(
                    "Jacktook [COLOR FFFF6B00]Jackett[/COLOR]", "Searching..."
                )
                response = jackett.search(query, mode, jackett_insecured)
            else:
                return None, None
        else:
            dialog.create("Jacktook [COLOR FFFF6B00]Jackett[/COLOR]", "Searching...")
            response = jackett.search(query, mode, jackett_insecured)

    elif indexer == Indexer.PROWLARR:
        indexers_ids = get_setting("prowlarr_indexer_ids")
        indexers_ids_list = indexers_ids.split() if indexers_ids else None

        anime_ids = get_setting("prowlarr_anime_indexer_ids")
        anime_indexers_ids_list = anime_ids.split() if anime_ids else None

        prowlarr = get_client()
        if not prowlarr:
            return None, None

        if not query:
            text = Keyboard(id=30243)
            if text:
                query = quote(text)
                dialog.create(
                    "Jacktook [COLOR FFFF6B00]Prowlarr[/COLOR]", "Searching..."
                )
                response = prowlarr.search(
                    query,
                    indexers_ids_list,
                    anime_indexers_ids_list,
                    mode,
                    prowlarr_insecured,
                )
            else:
                return None, None
        else:
            dialog.create("Jacktook [COLOR FFFF6B00]Prowlarr[/COLOR]", "Searching...")
            response = prowlarr.search(
                query,
                indexers_ids_list,
                anime_indexers_ids_list,
                mode,
                prowlarr_insecured,
            )

    return response, query
