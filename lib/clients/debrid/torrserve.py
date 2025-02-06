import requests
from requests.auth import HTTPBasicAuth
from requests.exceptions import RequestException
from urllib.parse import urlparse
from lib.api.jacktook.kodi import kodilog

class TorrServeException(Exception):
    pass

class TorrServeClient:
    def __init__(self, base_url="http://localhost:8090", username=None, password=None):
        # Validate and format base URL
        parsed = urlparse(base_url)
        if not parsed.scheme:
            base_url = f"http://{base_url}"
        elif parsed.scheme not in ("http", "https"):
            raise TorrServeException("Invalid URL scheme. Use http:// or https://")
            
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        
        if username and password:
            self.session.auth = HTTPBasicAuth(username, password)
        
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json"
        })

    def _request(self, method, endpoint, data=None):
        """Improved URL handling with better error messages"""
        try:
            # Construct safe URL
            endpoint = endpoint.lstrip("/")
            url = f"{self.base_url}/{endpoint}"
            
            # Validate URL format
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                raise TorrServeException(f"Invalid URL format: {url}")
            
            response = self.session.request(method, url, json=data)
            response.raise_for_status()
            return response.json()
        except RequestException as e:
            raise TorrServeException(f"Request to {url} failed: {str(e)}")
        except ValueError:
            raise TorrServeException(f"Invalid JSON response from {url}")

    def get_torrent_instant_availability(self, info_hashes):
        """
        Check availability of torrents by their info hashes
        
        Args:
            info_hashes (list): List of torrent info hashes (strings)
            
        Returns:
            dict: Dictionary with info_hash as key and availability percentage as value
        """
        kodilog(f"Checking availability for {info_hashes} torrents")
        try:
            # Get list of all torrents
            response = self._request("POST", "/torrents", {
                "action": "list"
            })
            
            available = {}
            hash_map = {}
            
            # Parse response (assuming array of TorrentStatus)
            for torrent in response:
                if "hash" in torrent:
                    t_hash = torrent["hash"].lower()
                    if not t_hash in info_hashes:
                        continue
                    status = torrent.get("stat", 0)
                    
                    # Calculate completion percentage
                    size = torrent.get("torrent_size", 0)
                    loaded = torrent.get("preloaded_bytes", 0)
                    percentage = (loaded / size * 100) if size > 0 else 0
                    
                    hash_map[t_hash] = round(percentage, 2) if status == 3 else 0  # Only consider working torrents

            # Match requested hashes
            for ih in info_hashes:
                completion = hash_map.get(ih.lower(), 0)
                if not completion:
                    continue
                available[ih.lower()] = hash_map.get(ih.lower(), 0)
            
            return available
            
        except TorrServeException as e:
            raise TorrServeException(f"Availability check failed: {str(e)}")

    def add_magnet(self, magnet_uri, save_to_db=True, title=None, category=None):
        """
        Add a torrent by magnet URI
        
        Args:
            magnet_uri (str): Magnet URI to add
            save_to_db (bool): Save torrent to database
            title (str): Custom title for the torrent
            category (str): Torrent category (movie/tv/music/other)
            
        Returns:
            dict: Dictionary containing:
                - status: "added", "duplicate", or "error"
                - info_hash: Torrent info hash (lowercase)
                - percentage: Current download completion percentage
        """
        try:
            # Add torrent request
            payload = {
                "action": "add",
                "link": magnet_uri,
                "save_to_db": save_to_db
            }
            kodilog(f"Payload: {payload}")
            if title:
                payload["title"] = title
            if category:
                payload["category"] = category
                
            response = self._request("POST", "/torrents", payload)
            
            # Check response status
            status_code = response.get("stat", 0)
            info_hash = response.get("hash", "").lower()
            
            if not info_hash:
                raise TorrServeException("Missing info hash in response")
                
            # Determine status
            if status_code == 5:  # TorrentInDB
                status = "duplicate"
            elif status_code == 3:  # TorrentWorking
                status = "added"
            else:
                status = "unknown"
            
            # Calculate percentage
            size = response.get("torrent_size", 0)
            loaded = response.get("preloaded_bytes", 0)
            percentage = (loaded / size * 100) if size > 0 else 0
            
            return {
                "status": status,
                "info_hash": info_hash,
                "percentage": round(percentage, 2)
            }
            
        except TorrServeException as e:
            return {
                "status": "error",
                "info_hash": "",
                "percentage": 0,
                "error": str(e)
            }

    def get_torrent_status(self, info_hash):
        """
        Get detailed status of a specific torrent
        """
        try:
            response = self._request("POST", "/torrents", {
                "action": "get",
                "hash": info_hash
            })
            return response
        except TorrServeException as e:
            raise TorrServeException(f"Status check failed: {str(e)}")

    def remove_torrent(self, info_hash, remove_data=False):
        """
        Remove a torrent from the server
        """
        try:
            action = "rem" if not remove_data else "drop"
            self._request("POST", "/torrents", {
                "action": action,
                "hash": info_hash
            })
            return True
        except TorrServeException as e:
            raise TorrServeException(f"Removal failed: {str(e)}")