import hashlib
import ipaddress
import json
import socket
from datetime import timedelta
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
import xbmcgui

from lib.api.nuvio import NuvioClient
from lib.clients.nuvio.constants import (
    NUVIO_ADDONS_KEY,
    NUVIO_USER_ADDONS,
    decode_selected_ids,
    encode_selected_ids,
)
from lib.db.cached import cache
from lib.utils.general.utils import USER_AGENT_HEADER
from lib.utils.kodi.settings import get_int_setting
from lib.utils.kodi.utils import kodilog, translation

MAX_MANIFEST_BYTES = 512 * 1024
MAX_REDIRECTS = 5


def _safe_manifest_url(url):
    normalized = str(url or "").strip()
    if normalized.startswith("stremio://"):
        normalized = normalized.replace("stremio://", "https://", 1)
    parts = urlsplit(normalized)
    if (
        parts.scheme.lower() != "https"
        or not parts.hostname
        or parts.username
        or parts.password
        or parts.fragment
        or not parts.path.rstrip("/").endswith("/manifest.json")
    ):
        return ""
    return urlunsplit(("https", parts.netloc, parts.path, parts.query, ""))


def _is_safe_http_url(url):
    try:
        parts = urlsplit(str(url or ""))
        if (
            parts.scheme.lower() != "https"
            or not parts.hostname
            or parts.username
            or parts.password
        ):
            return False
        try:
            addresses = [str(ipaddress.ip_address(parts.hostname))]
        except ValueError:
            addresses = [entry[4][0] for entry in socket.getaddrinfo(parts.hostname, None)]
        return all(ipaddress.ip_address(address).is_global for address in addresses)
    except (OSError, ValueError):
        return False


def _request_with_safe_redirects(url):
    target = url
    for _ in range(MAX_REDIRECTS + 1):
        if not _is_safe_http_url(target):
            raise ValueError("unsafe request destination")
        response = requests.get(
            target,
            allow_redirects=False,
            headers=USER_AGENT_HEADER,
            timeout=get_int_setting("stremio_timeout"),
            stream=True,
        )
        if response.status_code not in {301, 302, 303, 307, 308}:
            return response
        location = (response.headers or {}).get("Location")
        if not location:
            return response
        target = urljoin(target, location)
    raise ValueError("too many redirects")


def _fetch_manifest(url):
    manifest_url = _safe_manifest_url(url)
    if not manifest_url or not _is_safe_http_url(manifest_url):
        raise ValueError("invalid manifest URL")
    response = _request_with_safe_redirects(manifest_url)
    response.raise_for_status()
    final_url = _safe_manifest_url(response.url)
    if not final_url or not _is_safe_http_url(final_url):
        raise ValueError("unsafe redirect")
    content_length = response.headers.get("Content-Length")
    if content_length and int(content_length) > MAX_MANIFEST_BYTES:
        raise ValueError("manifest too large")
    content = bytearray()
    for chunk in response.iter_content(chunk_size=8192):
        content.extend(chunk)
        if len(content) > MAX_MANIFEST_BYTES:
            raise ValueError("manifest too large")
    manifest = json.loads(content.decode("utf-8"))
    if not isinstance(manifest, dict) or not (manifest.get("id") or manifest.get("name")):
        raise ValueError("invalid manifest")
    if not isinstance(manifest.get("resources", []), (list, dict, str)):
        raise ValueError("invalid manifest resources")
    return manifest, final_url


def _addon_key(record):
    manifest = record.get("manifest") or {}
    addon_id = manifest.get("id") or record.get("name") or ""
    transport_url = record.get("transportUrl") or ""
    normalized = _safe_manifest_url(transport_url)
    if not normalized:
        return str(addon_id)
    parts = urlsplit(normalized)
    path = parts.path.rstrip("/")
    if path.endswith("/manifest.json"):
        path = path[: -len("/manifest.json")]
    base_url = urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))
    digest = hashlib.sha256(base_url.encode("utf-8")).hexdigest()[:16]
    return f"{addon_id}|{digest}" if addon_id else digest


def _build_options(records):
    options = []
    for record in records:
        manifest = record["manifest"]
        item = xbmcgui.ListItem(
            label=record.get("nuvioName") or manifest.get("name") or manifest.get("id"),
            label2=manifest.get("description", ""),
        )
        item.setArt({"icon": manifest.get("logo") or "DefaultAddon.png"})
        options.append(item)
    return options


def _show_addon_multiselect(records, selected_ids):
    selected = set(decode_selected_ids(selected_ids))
    preselect = [index for index, record in enumerate(records) if _addon_key(record) in selected]
    indexes = xbmcgui.Dialog().multiselect(
        translation(91019), _build_options(records), preselect=preselect, useDetails=True
    )
    if indexes is None:
        return None
    return [_addon_key(records[index]) for index in indexes]


def _merge_records(existing, imported):
    merged = []
    seen = set()
    for record in list(existing or []) + imported:
        if not isinstance(record, dict) or not isinstance(record.get("manifest"), dict):
            continue
        key = _addon_key(record)
        if key and key not in seen:
            merged.append(record)
            seen.add(key)
    return merged


def nuvio_toggle_addons(params=None):
    """Select enabled Nuvio addon manifests without changing Stremio state."""
    rows = NuvioClient().get_addons()
    if rows is None:
        xbmcgui.Dialog().ok(translation(91018), translation(91022))
        return
    imported = []
    for row in rows:
        try:
            manifest, manifest_url = _fetch_manifest(row["url"])
            imported.append(
                {
                    "manifest": manifest,
                    "transportUrl": manifest_url,
                    "transportName": "nuvio",
                    "nuvioName": row.get("name") or "",
                }
            )
        except (requests.RequestException, ValueError, UnicodeDecodeError):
            kodilog("[NUVIO] skipped unavailable or invalid addon manifest")
    if not imported:
        xbmcgui.Dialog().ok(translation(91018), translation(91021))
        return
    selected = _show_addon_multiselect(imported, cache.get(NUVIO_ADDONS_KEY))
    if selected is None:
        return
    existing = cache.get(NUVIO_USER_ADDONS) or []
    cache.set(NUVIO_USER_ADDONS, _merge_records(existing, imported), timedelta(days=365 * 20))
    cache.set(NUVIO_ADDONS_KEY, encode_selected_ids(selected), timedelta(days=365 * 20))
