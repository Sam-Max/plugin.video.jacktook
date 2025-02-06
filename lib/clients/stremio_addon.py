from lib.clients.base import BaseClient
from lib.utils.client_utils import show_dialog
from lib.utils.utils import USER_AGENT_HEADER, IndexerType, info_hash_to_magnet
from lib.stremio.addons_manager import Addon
from lib.stremio.stream import Stream
from lib.api.jacktook.kodi import kodilog



class StremioAddonCatalogsClient(BaseClient):
    def __init__(self, params):
        super().__init__(None, None)
        self.params = params
        self.base_url = self.params["addon_url"]

    def search(self, imdb_id, mode, media_type, season, episode, dialog):
        pass

    def parse_response(self, res):
        pass

    def get_catalog_info(self, skip, force_refresh=False):
        url = f"{self.base_url}/catalog/{self.params['catalog_type']}/{self.params['catalog_id']}/skip={skip}.json"
        kodilog(url)
        res = self.session.get(url, headers=USER_AGENT_HEADER, timeout=10)
        if res.status_code != 200:
            return
        return res.json()
    
    def get_meta_info(self):
        url = f"{self.base_url}/meta/{self.params['catalog_type']}/{self.params['video_id']}.json"
        kodilog(url)
        res = self.session.get(url, headers=USER_AGENT_HEADER, timeout=10)
        if res.status_code != 200:
            return
        return res.json()
    
    def get_stream_info(self):
        url = f"{self.base_url}/stream/{self.params['catalog_type']}/{self.params['video_id']}.json"
        kodilog(url)
        res = self.session.get(url, headers=USER_AGENT_HEADER, timeout=10)
        if res.status_code != 200:
            return
        return res.json()
    

class StremioAddonClient(BaseClient):
    def __init__(self, addon: Addon):
        super().__init__(None, None)
        self.addon = addon
        self.addon_name = self.addon.manifest.name

    def search(self, imdb_id, mode, media_type, season, episode, dialog):
        show_dialog(self.addon_name, f"Searching {self.addon_name}", dialog)
        try:
            if mode == "tv" or media_type == "tv":
                if not self.addon.isSupported("stream", "series", "tt"):
                    return []
                url = f"{self.addon.url()}/stream/series/{imdb_id}:{season}:{episode}.json"
            elif mode == "movies" or media_type == "movies":
                if not self.addon.isSupported("stream", "movie", "tt"):
                    return []
                url = f"{self.addon.url()}/stream/movie/{imdb_id}.json"
            res = self.session.get(url, headers=USER_AGENT_HEADER, timeout=10)
            if res.status_code != 200:
                return
            return self.parse_response(res)
        except Exception as e:
            self.handle_exception(f"Error in {self.addon_name}: {str(e)}")

    def parse_response(self, res):
        res = res.json()
        results = []
        for item in res["streams"]:
            stream = Stream(item)
            results.append(
                {
                    "title": stream.get_parsed_title(),
                    "type": (
                        IndexerType.STREMIO_DEBRID
                        if stream.url
                        else IndexerType.TORRENT
                    ),
                    "description": stream.description,
                    "url": stream.url,
                    "indexer": self.addon.manifest.name.split(" ")[0],
                    "guid": stream.infoHash,
                    "magnet": info_hash_to_magnet(stream.infoHash),
                    "info_hash": stream.infoHash,
                    "size": stream.get_parsed_size() or item.get("sizebytes"),
                    "seeders": item.get("seed", 0),
                    "languages": [item.get("language")] if item.get("language") else [],
                    "fullLanguages": [item.get("language")] if item.get("language") else [],
                    "provider": "",
                    "publishDate": "",
                    "peers": 0,
                }
            )
        return results