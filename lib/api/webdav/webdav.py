import os
from urllib.parse import unquote, urlparse
import requests
from requests.auth import HTTPBasicAuth
import xml.etree.ElementTree as ET
from lib.utils.kodi.utils import kodilog


VIDEO_EXTS = {
    ".mkv",
    ".mp4",
    ".avi",
    ".mov",
    ".ts",
    ".m2ts",
    ".wmv",
    ".flv",
    ".webm",
    ".iso",
}
AUDIO_EXTS = {".mp3", ".flac", ".wav", ".aac", ".m4a", ".ogg", ".wma", ".opus"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".ico"}
TEXT_EXTS = {".txt", ".log", ".nfo", ".xml", ".json", ".md", ".srt"}


class WebDAVClient:
    def __init__(
        self, hostname, username=None, password=None, port=None, remote_path=None
    ):
        self.username = username
        self.password = password

        hostname = hostname.strip().rstrip("/")

        if hostname.startswith("http://") or hostname.startswith("https://"):
            base = hostname
        else:
            base = "http://" + hostname

        remote_path = remote_path.strip("/") if remote_path else ""

        self.server_root = f"{base}:{port}"
        self.api_root = f"{self.server_root}/webdav"
        if remote_path:
            self.api_root = f"{self.api_root}/{remote_path}"

        self.auth = HTTPBasicAuth(username, password) if username and password else None

    def _get_file_type(self, filename):
        """Determine file type based on extension."""
        _, ext = os.path.splitext(filename)
        ext = ext.lower()

        if ext in VIDEO_EXTS:
            return "video"
        elif ext in AUDIO_EXTS:
            return "audio"
        elif ext in IMAGE_EXTS:
            return "image"
        elif ext in TEXT_EXTS:
            return "text"
        return "file"

    def list_dir(self, relative_path=""):
        url = f"{self.api_root}/{relative_path}".strip("/") + "/"

        headers = {"Depth": "1"}
        try:
            r = requests.request("PROPFIND", url, headers=headers, auth=self.auth)
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            kodilog(f"WebDAV Error: {e}")
            return []

        tree = ET.fromstring(r.text)
        items = []
        requested_path_norm = unquote(urlparse(url).path).rstrip("/")

        for resp in tree.findall(".//{DAV:}response"):
            href_elem = resp.find("{DAV:}href")
            if href_elem is None:
                continue

            href = href_elem.text
            href_decoded = unquote(href)
            href_path_norm = urlparse(href_decoded).path.rstrip("/")

            if href_path_norm == requested_path_norm:
                continue

            name = href_path_norm.split("/")[-1]
            if not name:
                continue

            # Determine if it's a folder
            is_directory = href.endswith("/")
            res_type = resp.find(".//{DAV:}resourcetype")
            if res_type is not None and res_type.find("{DAV:}collection") is not None:
                is_directory = True

            if is_directory:
                items.append({"name": name, "type": "folder"})
            else:
                # Detect specific file type
                file_type = self._get_file_type(name)

                # Build Auth URL
                creds = (
                    f"{self.username}:{self.password}@"
                    if self.username and self.password
                    else ""
                )
                clean_host = self.server_root.replace("http://", "").replace(
                    "https://", ""
                )
                file_url = f"http://{creds}{clean_host}{href}"

                items.append(
                    {
                        "name": name,
                        "type": file_type,
                        "url": file_url,
                    }
                )

        return items

    def test_connection(self):
        if not self.api_root:
            return {"success": False, "message": "WebDAV hostname not set."}

        try:
            headers = {"Depth": "1"}
            r = requests.request(
                "PROPFIND", self.api_root, headers=headers, auth=self.auth, timeout=10
            )
            r.raise_for_status()

            # Parse XML to make sure server responded properly
            ET.fromstring(r.text)

            return {
                "success": True,
                "message": f"WebDAV server reachable",
            }

        except requests.exceptions.RequestException as e:
            return {"success": False, "message": f"Connection failed"}
        except ET.ParseError:
            return {"success": False, "message": "Invalid response from WebDAV server."}
