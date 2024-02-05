import json
from urllib.parse import quote
import requests
from resources.lib.kodi import Keyboard, get_setting, log, notify, translation
from resources.lib.utils import Indexer
from urllib3.exceptions import InsecureRequestWarning
from resources.lib import xmltodict


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

    def search(self, query, mode, season, episode, insecure=False):
        try:
            if mode == "tv":
                url = f"{self.host}/api/v2.0/indexers/all/results/torznab/api?apikey={self.apikey}&t=tvsearch&q={query}&season={season}&ep={episode}"
                log(url)
            elif mode == "movie":
                url = f"{self.host}/api/v2.0/indexers/all/results/torznab/api?apikey={self.apikey}&t=movie&q={query}"
            elif mode == "anime":
                url = f"{self.host}/api/v2.0/indexers/nyaasi/results/torznab/api?apikey={self.apikey}&t=search&q={query}"
            elif mode == "multi":
                url = f"{self.host}/api/v2.0/indexers/all/results/torznab/api?apikey={self.apikey}&t=search&q={query}"
            res = requests.get(url, verify=insecure)
            if res.status_code != 200:
                notify(f"{translation(30229)} ({res.status_code})")
                return
            return self._parse_response(res)
        except Exception as e:
            notify(f"{translation(30229)} {str(e)}")

    def _parse_response(self, res):
        res = xmltodict.parse(res.content)
        if "item" in res["rss"]["channel"]:
            items = res["rss"]["channel"]["item"]
            results = []
            for item in items:
                for sub_item in item["torznab:attr"]:
                    if sub_item["@name"] == "seeders":
                        seeders = sub_item["@value"]
                    elif sub_item["@name"] == "peers":
                        peers = sub_item["@value"]
                    elif sub_item["@name"] == "magneturl":
                        magnetUrl = sub_item["@value"]
                    elif sub_item["@name"] == "infohash":
                        infohash = sub_item["@value"]
                results.append(
                    {
                        "qtTitle": "",
                        "title": item["title"],
                        "indexer": item["jackettindexer"]["#text"],
                        "publishDate": item["pubDate"],
                        "guid": item["guid"],
                        "downloadUrl": item["link"],
                        "size": item["size"],
                        "magnetUrl": magnetUrl,
                        "seeders": seeders,
                        "peers": peers,
                        "infoHash": infohash,
                        "rdId": "",
                        "rdCached": False,
                        "rdLinks": [],
                    }
                )
            return results


class Prowlarr:
    def __init__(self, host, apikey) -> None:
        self.host = host
        self.apikey = apikey

    def search(self, query, mode, season, episode, indexers, anime_indexers, insecure=False):
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Api-Key": self.apikey,
        }
        try:
            if mode == "tv":
                query = f"{query} S{season}E{episode}"
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
            res = json.loads(res.text)
            for r in res:
                r.update(
                    {
                        "qtTitle": "",
                        "rdId": "",
                        "rdCached": False,
                        "rdLinks": [],
                    }
                )
            return res
        except Exception as e:
            notify(f"{translation(30230)} {str(e)}")
            return


def search_api(query, mode, dialog, season=1, episode=1):
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
                response = jackett.search(
                    query, mode, season, episode, jackett_insecured
                )
            else:
                dialog.create("")
                return None, None
        else:
            dialog.create("Jacktook [COLOR FFFF6B00]Jackett[/COLOR]", "Searching...")
            response = jackett.search(
                query, mode, season, episode, jackett_insecured
            )

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
                    mode,
                    season, 
                    episode, 
                    indexers_ids_list,
                    anime_indexers_ids_list,
                    prowlarr_insecured,
                )
            else:
                dialog.create("")
                return None, None
        else:
            dialog.create("Jacktook [COLOR FFFF6B00]Prowlarr[/COLOR]", "Searching...")
            response = prowlarr.search(
                query,
                mode,
                season, 
                episode,
                indexers_ids_list,
                anime_indexers_ids_list,
                prowlarr_insecured,
            )

    return response, query
