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
        kodilog(f"WebDAV Client initialized with hostname: {hostname}")

        hostname = hostname.strip().rstrip("/")

        if hostname.startswith("http://") or hostname.startswith("https://"):
            base = hostname
        else:
            base = "http://" + hostname

        # Store scheme for URL construction
        self.scheme = "https" if base.startswith("https://") else "http"

        remote_path = remote_path.strip("/") if remote_path else ""

        if port and str(port).strip():
            # Check if port is already in hostname
            if ":" in hostname.replace("://", ""):
                self.server_root = base
            else:
                self.server_root = f"{base}:{port}"
        else:
            self.server_root = base

        # Use remote_path if provided, otherwise server_root
        if remote_path:
            self.api_root = f"{self.server_root}/{remote_path}"
        else:
            self.api_root = self.server_root

        kodilog(f"WebDAV Server Root: {self.server_root}")
        kodilog(f"WebDAV API Root: {self.api_root}")

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
        # Construct URL carefully to avoid double slashes but ensure trailing slash for PROPFIND
        path_parts = [self.api_root]
        if relative_path:
            path_parts.append(relative_path.strip("/"))

        url = "/".join(path_parts).rstrip("/") + "/"
        kodilog(f"WebDAV URL: {url}")

        headers = {"Depth": "1"}
        try:
            r = requests.request(
                "PROPFIND", url, headers=headers, auth=self.auth, timeout=15
            )
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            # Check if it's an HTTP error with a response
            if hasattr(e, "response") and e.response is not None:
                kodilog(f"WebDAV Error {e.response.status_code}: {e}")
                kodilog(f"WebDAV Error Response Content: {e.response.text[:500]}")
            else:
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

                # Extract only the path from href to avoid issues with absolute URLs
                # (e.g. server returning http://localhost:8080/...)
                href_path = urlparse(href).path
                file_url = (
                    f"{self.scheme}://{creds}{clean_host}/{href_path.lstrip('/')}"
                )

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

        # Ensure trailing slash for directory PROPFIND
        url = self.api_root.rstrip("/") + "/"

        try:
            headers = {"Depth": "1"}
            kodilog(f"Testing connection to {url}")
            r = requests.request(
                "PROPFIND", url, headers=headers, auth=self.auth, timeout=10
            )
            r.raise_for_status()

            # Parse XML to make sure server responded properly
            ET.fromstring(r.text)

            return {
                "success": True,
                "message": f"WebDAV server reachable",
            }

        except requests.exceptions.RequestException as e:
            msg = f"Connection failed: {e}"
            if hasattr(e, "response") and e.response is not None:
                msg = f"WebDAV Error {e.response.status_code}: {e}"
                kodilog(f"Test Connection Response Content: {e.response.text[:500]}")
            kodilog(msg)
            return {"success": False, "message": msg}
        except ET.ParseError:
            return {
                "success": False,
                "message": "Invalid response from WebDAV server. (Not XML)",
            }
