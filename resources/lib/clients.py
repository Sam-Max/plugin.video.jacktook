import json
import re
from urllib.parse import quote
import requests
from resources.lib.kodi import (
    Keyboard,
    convert_size_to_bytes,
    get_setting,
    log,
    notify,
    translation,
)
from resources.lib.utils import Indexer
from urllib3.exceptions import InsecureRequestWarning
from resources.lib import xmltodict


def get_client(indexer):
    if indexer == Indexer.JACKETT:
        host = get_setting("jackett_host")
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
        api_key = get_setting("prowlarr_apikey")

        if not host or not api_key:
            notify(translation(30223))
            return

        if len(api_key) != 32:
            notify(translation(30224))
            return

        return Prowlarr(host, api_key)

    elif indexer == Indexer.TORRENTIO:
        host = get_setting("torrentio_host")

        if not host:
            notify(translation(30227))
            return

        return Torrentio(host)


class Torrentio:
    def __init__(self, host) -> None:
        self.host = host

    def search(self, id, mode, season, episode, insecure=False):
        try:
            if mode == "tv":
                url = f"{self.host}/stream/{mode}/{id}:{season}:{episode}.json"
            elif mode in ["movie", "multi"]:
                url = f"{self.host}/stream/{mode}/{id}.json"
            res = requests.get(url, verify=insecure)
            if res.status_code != 200:
                return
            response = self.parse_response(res)
            return response
        except Exception as e:
            log(str(e))
            notify(f"{translation(30228)}: {str(e)}")

    def parse_response(self, res):
        res = json.loads(res.text)
        results = []
        for item in res["streams"]:
            parsed_item = self.parse_stream_title(item["title"])
            results.append(
                {
                    "title": parsed_item["title"],
                    "qtTitle": "",
                    "indexer": "Torrentio",
                    "guid": item["infoHash"],
                    "infoHash": item["infoHash"],
                    "size": parsed_item["size"],
                    "seeders": parsed_item["seeders"],
                    "publishDate": "",
                    "peers": 0,
                    "rdId": "",
                    "rdCached": False,
                    "rdLinks": [],
                }
            )
        return results

    def parse_stream_title(self, title):
        name = title.splitlines()[0]

        size_match = re.search(r"💾 (\d+(?:\.\d+)?\s*(GB|MB))", title, re.IGNORECASE)
        size = size_match.group(1) if size_match else ""
        size = convert_size_to_bytes(size)

        seeders_match = re.search(r"👤 (\d+)", title)
        seeders = int(seeders_match.group(1)) if seeders_match else None

        return {
            "title": name,
            "size": size,
            "seeders": seeders,
            "languages": self.extract_languages(title),
        }

    def extract_languages(self, title):
        languages = []
        if "Multi Audio" in title or "Multi Language" in title:
            languages.append("Multi Language")
        elif "Dual Audio" in title or "Dual Language" in title:
            languages.append("Dual Language")
        # Regex to match country flag emojis
        flag_emojis = re.findall(r"[\U0001F1E6-\U0001F1FF]{2}", title)
        if flag_emojis:
            languages.extend(flag_emojis)
        return languages


class Jackett:
    def __init__(self, host, apikey) -> None:
        self.host = host.rstrip("/")
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
            return self.parse_response(res)
        except Exception as e:
            notify(f"{translation(30229)} {str(e)}")

    def parse_response(self, res):
        res = xmltodict.parse(res.content)
        if "item" in res["rss"]["channel"]:
            items = res["rss"]["channel"]["item"]
            magnetUrl = ""
            infohash = ""
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
        self.host = host.rstrip("/")
        self.apikey = apikey

    def search(
        self, query, mode, season, episode, indexers, anime_indexers, insecure=False
    ):
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Api-Key": self.apikey,
        }
        try:
            if mode == "tv":
                query = f"{query} S{int(season):02}E{int(episode):02}"
                url = f"{self.host}/api/v1/search?query={query}&categories=5000"
            elif mode == "movie":
                url = f"{self.host}/api/v1/search?query={query}&categories=2000"
            elif mode == "anime":
                if anime_indexers:
                    anime_indexers_url = "".join(
                        [f"&indexerIds={index}" for index in anime_indexers]
                    )
                    url = f"{self.host}/api/v1/search?query={query}{anime_indexers_url}"
                else:
                    notify(translation(30231))
                    return
            elif mode == "multi":
                url = f"{self.host}/api/v1/search?query={query}"
            if indexers:
                url = url + "".join([f"&indexerIds={index}" for index in indexers])
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


def search_api(query, imdb_id, mode, dialog, season=1, episode=1):
    query = None if query == "None" else query

    indexer = get_setting("indexer")
    jackett_insecured = get_setting("jackett_insecured")
    prowlarr_insecured = get_setting("prowlarr_insecured")
    if prowlarr_insecured or jackett_insecured:
        requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

    client = get_client(indexer)
    if not client:
        dialog.create("")
        return None, None

    if not query:
        text = Keyboard(id=30243)
        if text:
            query = quote(text)
        else:
            dialog.create("")
            return None, None

    if indexer == Indexer.JACKETT:
        dialog.create("Jacktook [COLOR FFFF6B00]Jackett[/COLOR]", "Searching...")
        response = client.search(query, mode, season, episode, jackett_insecured)

    elif indexer == Indexer.PROWLARR:
        indexers_ids = get_setting("prowlarr_indexer_ids")
        indexers_ids_list = indexers_ids.split() if indexers_ids else None

        anime_ids = get_setting("prowlarr_anime_indexer_ids")
        anime_indexers_ids_list = anime_ids.split() if anime_ids else None

        dialog.create("Jacktook [COLOR FFFF6B00]Prowlarr[/COLOR]", "Searching...")
        response = client.search(
            query,
            mode,
            season,
            episode,
            indexers_ids_list,
            anime_indexers_ids_list,
            prowlarr_insecured,
        )
    elif indexer == Indexer.TORRENTIO:
        if imdb_id == "-1":
            notify("Direct Search not supported for Torrentio")
            dialog.create("")
            return None, None
        dialog.create("Jacktook [COLOR FFFF6B00]Torrestio[/COLOR]", "Searching...")
        response = client.search(imdb_id, mode, season, episode)

    return response, query
