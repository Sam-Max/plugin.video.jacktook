# -*- coding: utf-8 -*-
"""
Local web server for managing Stremio addon sources from a phone/browser.

Serves a web UI and exposes small JSON endpoints for CRUD operations
on the Stremio custom addons stored in the Kodi addon cache.
"""
import json
import os
import socket
import threading
from datetime import timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler

import requests

from lib.db.cached import cache
from lib.utils.general.utils import USER_AGENT_HEADER
from lib.utils.kodi.utils import kodilog
from lib.clients.stremio.constants import (
    STREMIO_ADDONS_KEY,
    STREMIO_ADDONS_CATALOGS_KEY,
    STREMIO_TV_ADDONS_KEY,
    STREMIO_USER_ADDONS,
)

_CACHE_EXPIRY = timedelta(days=365 * 20)
_WEB_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "resources",
    "web",
)


# ---------------------------------------------------------------------------
# Sync helpers (no xbmcgui imports — safe for HTTP thread)
# ---------------------------------------------------------------------------


def _get_user_addons():
    """Return list of custom addon dicts from cache."""
    return [
        a
        for a in (cache.get(STREMIO_USER_ADDONS) or [])
        if a.get("transportName") == "custom"
    ]


def _get_selected_ids():
    """Return dict of selected addon IDs per category."""
    result = {}
    for key, label in [
        (STREMIO_ADDONS_KEY, "stream"),
        (STREMIO_ADDONS_CATALOGS_KEY, "catalog"),
        (STREMIO_TV_ADDONS_KEY, "tv"),
    ]:
        val = cache.get(key) or ""
        result[label] = [k for k in val.split(",") if k]
    return result


def _addon_capabilities(manifest):
    """Determine stream/catalog/tv capabilities from a manifest dict."""
    resources = manifest.get("resources", [])
    types = manifest.get("types", [])
    is_stream = False
    is_catalog = False
    is_tv = False

    for res in resources:
        if isinstance(res, dict):
            res_types = res.get("types", types)
            if res.get("name") == "stream":
                id_prefixes = res.get("idPrefixes", [])
                if "tt" in id_prefixes:
                    is_stream = True
                if "tv" in res_types or "channel" in res_types:
                    is_tv = True
            if res.get("name") == "catalog":
                is_catalog = True
        elif isinstance(res, str):
            if res == "stream":
                if "movie" in types or "series" in types:
                    is_stream = True
                if "tv" in types or "channel" in types:
                    is_tv = True
            if res == "catalog":
                is_catalog = True
    return {"stream": is_stream, "catalog": is_catalog, "tv": is_tv}


def _sync_add_addon(url):
    """Fetch manifest from URL, validate, store in cache.  Returns (addon_dict, error)."""
    if url.startswith("stremio://"):
        url = url.replace("stremio://", "https://")

    try:
        resp = requests.get(url, headers=USER_AGENT_HEADER, timeout=10)
        resp.raise_for_status()
        manifest = resp.json()
    except Exception as e:
        return None, f"Failed to fetch manifest: {e}"

    addon_key = manifest.get("id") or manifest.get("name")
    if not addon_key:
        return None, "Manifest missing 'id' or 'name'."

    # Check duplicate
    user_addons = cache.get(STREMIO_USER_ADDONS) or []
    if any(
        (a.get("manifest", {}).get("id") or a.get("manifest", {}).get("name"))
        == addon_key
        for a in user_addons
    ):
        return None, "This addon is already added."

    caps = _addon_capabilities(manifest)

    # Auto-select into categories
    if caps["stream"]:
        _add_to_selection(STREMIO_ADDONS_KEY, addon_key)
    if caps["catalog"]:
        _add_to_selection(STREMIO_ADDONS_CATALOGS_KEY, addon_key)
    if caps["tv"]:
        _add_to_selection(STREMIO_TV_ADDONS_KEY, addon_key)

    custom_addon = {
        "manifest": manifest,
        "transportUrl": resp.url,
        "transportName": "custom",
    }
    user_addons.append(custom_addon)
    cache.set(STREMIO_USER_ADDONS, user_addons, _CACHE_EXPIRY)

    return custom_addon, None


def _sync_remove_addon(addon_id):
    """Remove addon by manifest ID from all caches."""
    user_addons = cache.get(STREMIO_USER_ADDONS) or []
    new_addons = [
        a
        for a in user_addons
        if (a.get("manifest", {}).get("id") or a.get("manifest", {}).get("name"))
        != addon_id
    ]
    cache.set(STREMIO_USER_ADDONS, new_addons, _CACHE_EXPIRY)

    for cache_key in [
        STREMIO_ADDONS_KEY,
        STREMIO_ADDONS_CATALOGS_KEY,
        STREMIO_TV_ADDONS_KEY,
    ]:
        selected = cache.get(cache_key)
        if selected:
            keys = [k for k in selected.split(",") if k != addon_id]
            cache.set(cache_key, ",".join(keys), _CACHE_EXPIRY)


def _sync_toggle_addon(addon_id, category, enabled):
    """Add or remove addon_id from a selection category."""
    key_map = {
        "stream": STREMIO_ADDONS_KEY,
        "catalog": STREMIO_ADDONS_CATALOGS_KEY,
        "tv": STREMIO_TV_ADDONS_KEY,
    }
    cache_key = key_map.get(category)
    if not cache_key:
        return

    selected = cache.get(cache_key) or ""
    keys = [k for k in selected.split(",") if k]

    if enabled and addon_id not in keys:
        keys.append(addon_id)
    elif not enabled and addon_id in keys:
        keys.remove(addon_id)

    cache.set(cache_key, ",".join(keys), _CACHE_EXPIRY)


def _add_to_selection(cache_key, addon_id):
    selected = cache.get(cache_key) or ""
    keys = [k for k in selected.split(",") if k]
    if addon_id not in keys:
        keys.append(addon_id)
        cache.set(cache_key, ",".join(keys), _CACHE_EXPIRY)


def _validate_manifest(url):
    """Fetch and validate a manifest URL.  Returns (manifest_dict, error)."""
    if url.startswith("stremio://"):
        url = url.replace("stremio://", "https://")
    try:
        resp = requests.get(url, headers=USER_AGENT_HEADER, timeout=10)
        resp.raise_for_status()
        manifest = resp.json()
    except Exception as e:
        return None, str(e)

    if not manifest.get("id") and not manifest.get("name"):
        return None, "Manifest missing 'id' and 'name'."
    return manifest, None


# ---------------------------------------------------------------------------
# HTTP request handler
# ---------------------------------------------------------------------------


class StremioRequestHandler(BaseHTTPRequestHandler):
    """Handles web UI + JSON API requests."""

    def log_message(self, format, *args):
        kodilog(f"[WebServer] {format % args}")

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html_content):
        body = html_content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length else {}

    # --- Routes ---

    def do_GET(self):
        if self.path == "/" or self.path == "":
            self._serve_index()
        elif self.path == "/api/addons":
            self._api_get_addons()
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/addons":
            self._api_add_addon()
        elif self.path == "/api/addons/validate":
            self._api_validate()
        else:
            self.send_error(404)

    def do_DELETE(self):
        if self.path.startswith("/api/addons/"):
            addon_id = self.path[len("/api/addons/") :]
            self._api_remove_addon(addon_id)
        else:
            self.send_error(404)

    def do_PUT(self):
        if self.path.startswith("/api/addons/") and self.path.endswith("/toggle"):
            addon_id = self.path[len("/api/addons/") : -len("/toggle")]
            self._api_toggle_addon(addon_id)
        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header(
            "Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS"
        )
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    # --- Handlers ---

    def _serve_index(self):
        index_path = os.path.join(_WEB_DIR, "index.html")
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                self._send_html(f.read())
        except FileNotFoundError:
            self.send_error(500, "Web UI not found")

    def _api_get_addons(self):
        addons = _get_user_addons()
        selected = _get_selected_ids()
        result = []
        for a in addons:
            manifest = a.get("manifest", {})
            addon_key = manifest.get("id") or manifest.get("name") or ""
            caps = _addon_capabilities(manifest)
            result.append(
                {
                    "id": addon_key,
                    "name": manifest.get("name", "Unknown"),
                    "description": manifest.get("description", ""),
                    "logo": manifest.get("logo", ""),
                    "version": manifest.get("version", ""),
                    "types": manifest.get("types", []),
                    "transportUrl": a.get("transportUrl", ""),
                    "capabilities": caps,
                    "selected": {
                        "stream": addon_key in selected.get("stream", []),
                        "catalog": addon_key in selected.get("catalog", []),
                        "tv": addon_key in selected.get("tv", []),
                    },
                }
            )
        self._send_json({"addons": result})

    def _api_add_addon(self):
        try:
            data = self._read_body()
        except Exception:
            self._send_json({"error": "Invalid JSON"}, 400)
            return
        url = data.get("url", "").strip()
        if not url:
            self._send_json({"error": "URL is required"}, 400)
            return
        addon, error = _sync_add_addon(url)
        if error:
            self._send_json({"error": error}, 400)
            return
        manifest = addon.get("manifest", {})
        addon_key = manifest.get("id") or manifest.get("name") or ""
        caps = _addon_capabilities(manifest)
        self._send_json(
            {
                "success": True,
                "addon": {
                    "id": addon_key,
                    "name": manifest.get("name", "Unknown"),
                    "description": manifest.get("description", ""),
                    "logo": manifest.get("logo", ""),
                    "version": manifest.get("version", ""),
                    "types": manifest.get("types", []),
                    "transportUrl": addon.get("transportUrl", ""),
                    "capabilities": caps,
                    "selected": caps,
                },
            }
        )

    def _api_remove_addon(self, addon_id):
        from urllib.parse import unquote

        addon_id = unquote(addon_id)
        _sync_remove_addon(addon_id)
        self._send_json({"success": True})

    def _api_toggle_addon(self, addon_id):
        from urllib.parse import unquote

        addon_id = unquote(addon_id)
        try:
            data = self._read_body()
        except Exception:
            self._send_json({"error": "Invalid JSON"}, 400)
            return
        category = data.get("category")
        enabled = data.get("enabled", False)
        if category not in ("stream", "catalog", "tv"):
            self._send_json({"error": "Invalid category"}, 400)
            return
        _sync_toggle_addon(addon_id, category, enabled)
        self._send_json({"success": True})

    def _api_validate(self):
        try:
            data = self._read_body()
        except Exception:
            self._send_json({"error": "Invalid JSON"}, 400)
            return
        url = data.get("url", "").strip()
        if not url:
            self._send_json({"error": "URL is required"}, 400)
            return
        manifest, error = _validate_manifest(url)
        if error:
            self._send_json({"error": error}, 400)
            return
        self._send_json({"valid": True, "manifest": manifest})


# ---------------------------------------------------------------------------
# Server lifecycle
# ---------------------------------------------------------------------------


class StremioWebServer:
    """Threaded HTTP server that starts/stops on demand."""

    def __init__(self, port=8081):
        self.port = port
        self._server = None
        self._thread = None

    def start(self):
        if self._server:
            return
        try:
            self._server = HTTPServer(("0.0.0.0", self.port), StremioRequestHandler)
            self._thread = threading.Thread(
                target=self._server.serve_forever, daemon=True
            )
            self._thread.start()
            kodilog(f"[WebServer] Started on port {self.port}")
        except Exception as e:
            kodilog(f"[WebServer] Failed to start: {e}")
            self._server = None

    def stop(self):
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
            self._thread = None
            kodilog("[WebServer] Stopped")

    @property
    def is_running(self):
        return self._server is not None


def get_local_ip():
    """Get the machine's LAN IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"
