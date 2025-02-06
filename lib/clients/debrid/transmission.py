import requests
from lib.utils.kodi_utils import notification
from requests.exceptions import RequestException
from lib.domain.interface.cache_provider_interface import CacheProviderInterface
from lib.domain.cached_source import CachedSource
from typing import Dict, List
from lib.api.jacktook.kodi import kodilog
from lib.domain.source import Source
from lib.utils.kodi_formats import is_video

class TransmissionException(Exception):
    pass

class TransmissionClient(CacheProviderInterface):
    def __init__(self, base_url: str = "http://192.168.1.130:9091", downloads_url: str = "", username: str = "", password: str = ""):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session_id = None
        self.downloads_url = downloads_url.rstrip("/")
        self.session.headers.update({"Content-Type": "application/json", "Accept": "application/json"})
        if username and password:
            self.session.auth = (username, password)

    def _rpc_request(self, method, arguments=None):
        url = f"{self.base_url}/transmission/rpc"
        payload = {"method": method, "arguments": arguments or {}}
        
        for _ in range(2):  # Allow one retry after 409
            try:
                response = self.session.post(url, json=payload)
                if response.status_code == 409:
                    self.session_id = response.headers.get("X-Transmission-Session-Id")
                    if self.session_id:
                        self.session.headers["X-Transmission-Session-Id"] = self.session_id
                        continue  # Retry with new session ID
                    raise TransmissionException("Missing session ID in 409 response")
                
                response.raise_for_status()
                data = response.json()
                if data.get("result") != "success":
                    raise TransmissionException(f"RPC error: {data.get('result')}")
                
                return data.get("arguments", {})
            
            except (RequestException, ValueError) as e:
                raise TransmissionException(f"Request failed: {str(e)}")
        
        raise TransmissionException("Failed after session ID retry")

    def get_torrent_instant_availability(self, info_hashes):
        try:
            torrents = self._rpc_request("torrent-get", {"fields": ["hashString", "percentDone"]}).get("torrents", [])
            hash_map = {t["hashString"].lower(): t["percentDone"] for t in torrents}
            return {ih: round(hash_map[ih.lower()] * 100, 2) for ih in info_hashes if ih.lower() in hash_map}
        except TransmissionException as e:
            notification(f"Transmission error: {str(e)}")
            raise

    def add_magnet(self, magnet_uri: str):
        try:
            response = self._rpc_request("torrent-add", {"filename": magnet_uri, "paused": False})
            if "torrent-added" in response:
                torrent = response["torrent-added"]
                return {"status": "added", "info_hash": torrent["hashString"].lower()}
            elif "torrent-duplicate" in response:
                torrent = response["torrent-duplicate"]
                return {
                    "status": "duplicate",
                    "info_hash": torrent["hashString"].lower(),
                    "percentage": round(torrent["percentDone"] * 100, 2),
                }
            raise TransmissionException("Unexpected response structure")
        except TransmissionException as e:
            notification(f"Failed to add magnet: {str(e)}")
            raise

    def get_cached_hashes(self, sources: List[Source]) -> Dict[str, CachedSource]:
        info_hashes = {source["info_hash"]: source.get("filename", "") for source in sources if source.get("info_hash")}
        cached_sources = {}
        
        try:
            torrents = self._rpc_request("torrent-get", {"fields": ["hashString", "percentDone", "files"]}).get("torrents", [])
            kodilog(f"TransmissionClient: {len(torrents)} torrents found")
            
            for t in torrents:
                t_hash = t["hashString"]
                if t_hash not in info_hashes:
                    continue
                
                filename = info_hashes[t_hash]
                
                t_files = [f"{self.downloads_url}/{file['name']}" for file in t.get("files", [])]
                
                first_video = ""
                playable_url = ""
                for file in t_files:
                    if filename and file.endswith(filename):
                        playable_url = file
                        break
                    if not first_video and is_video(file):
                        first_video = file
                
                if not playable_url:
                    playable_url = first_video
                
                cached_sources[t["hashString"]] = CachedSource(
                    hash=t["hashString"].lower(),
                    cache_provider=self,
                    cache_provider_name="Transmission",
                    ratio=t["percentDone"],
                    instant_availability=t["percentDone"] == 1,
                    urls=t_files,
                    playable_url=playable_url,
                )
            
            return cached_sources
        
        except TransmissionException as e:
            notification(f"Transmission error: {str(e)}")
            raise