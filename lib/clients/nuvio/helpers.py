import hashlib
from typing import List
from urllib.parse import urlsplit, urlunsplit

from lib.api.stremio.addon_manager import Addon, AddonManager, build_legacy_addon_instance_key
from lib.clients.nuvio.constants import NUVIO_ADDONS_KEY, NUVIO_USER_ADDONS, decode_selected_ids
from lib.db.cached import cache
from lib.utils.kodi.utils import kodilog


def _safe_cache_get(key):
    """Return ``cache.get(key)`` tolerating unavailable/broken cache backends."""
    try:
        return cache.get(key)
    except Exception:
        return None


def _resolve_selected_addons(catalog: AddonManager, selected_ids: List[str]) -> List[Addon]:
    addons_by_key = {addon.key(): addon for addon in catalog.addons}
    addons_by_key.update(
        {build_legacy_addon_instance_key(addon): addon for addon in catalog.addons}
    )
    selected = []
    seen = set()
    for addon_key in selected_ids:
        addon = addons_by_key.get(addon_key)
        if addon and addon.key() not in seen:
            selected.append(addon)
            seen.add(addon.key())
    return selected


def _record_key(record):
    manifest = record.get("manifest") or {}
    addon_id = manifest.get("id") or record.get("name") or ""
    parts = urlsplit(str(record.get("transportUrl") or ""))
    path = parts.path.rstrip("/")
    if path.endswith("/manifest.json"):
        path = path[: -len("/manifest.json")]
    normalized_url = urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))
    if addon_id and normalized_url:
        return f"{addon_id}|{hashlib.sha256(normalized_url.encode('utf-8')).hexdigest()[:16]}"
    return addon_id


def _has_stream_resource(manifest):
    resources = manifest.get("resources", []) if isinstance(manifest, dict) else []
    if isinstance(resources, str):
        return resources == "stream"
    if not isinstance(resources, list):
        return False
    return any(
        resource == "stream" or (isinstance(resource, dict) and resource.get("name") == "stream")
        for resource in resources
    )


def get_selected_stream_addon_records():
    """Return Nuvio-owned display records without invoking the Stremio parser."""
    records = _safe_cache_get(NUVIO_USER_ADDONS) or []
    selected = set(decode_selected_ids(_safe_cache_get(NUVIO_ADDONS_KEY)))
    if not isinstance(records, list) or not selected:
        return []
    selected_records = []
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("manifest"), dict):
            continue
        key = _record_key(record)
        if key not in selected or not _has_stream_resource(record["manifest"]):
            continue
        selected_records.append(
            {
                "key": key,
                "name": record.get("nuvioName")
                or record["manifest"].get("name")
                or record["manifest"].get("id"),
            }
        )
    return selected_records


def get_selected_stream_addons() -> List[Addon]:
    """Load only Nuvio-owned selected manifests for Stremio protocol execution."""
    records = _safe_cache_get(NUVIO_USER_ADDONS) or []
    if not isinstance(records, list):
        return []
    catalog = AddonManager(records)
    selected = _resolve_selected_addons(
        catalog, decode_selected_ids(_safe_cache_get(NUVIO_ADDONS_KEY))
    )
    stream_addons = [
        addon
        for addon in selected
        if any(resource.name == "stream" for resource in addon.manifest.resources)
    ]
    kodilog(f"Loaded {len(stream_addons)} selected Nuvio stream addons")
    return stream_addons


def _has_catalog_resource(addon: Addon) -> bool:
    for resource in addon.manifest.resources:
        name = resource if isinstance(resource, str) else resource.name
        if name == "catalog":
            return True
    return False


def _is_tv_stream_addon(addon: Addon) -> bool:
    manifest_types = addon.manifest.types or []
    for resource in addon.manifest.resources:
        if isinstance(resource, str):
            if resource == "stream" and ("tv" in manifest_types or "channel" in manifest_types):
                return True
        elif resource.name == "stream" and ("tv" in resource.types or "channel" in resource.types):
            return True
    return False


def get_selected_catalogs_addons() -> List[Addon]:
    """Load Nuvio-owned selected manifests exposing a catalog resource."""
    records = _safe_cache_get(NUVIO_USER_ADDONS) or []
    if not isinstance(records, list):
        return []
    catalog = AddonManager(records)
    selected = _resolve_selected_addons(
        catalog, decode_selected_ids(_safe_cache_get(NUVIO_ADDONS_KEY))
    )
    catalog_addons = [addon for addon in selected if _has_catalog_resource(addon)]
    kodilog(f"Loaded {len(catalog_addons)} selected Nuvio catalog addons")
    return catalog_addons


def get_selected_tv_addons() -> List[Addon]:
    """Load Nuvio-owned selected manifests exposing tv/channel streams."""
    records = _safe_cache_get(NUVIO_USER_ADDONS) or []
    if not isinstance(records, list):
        return []
    catalog = AddonManager(records)
    selected = _resolve_selected_addons(
        catalog, decode_selected_ids(_safe_cache_get(NUVIO_ADDONS_KEY))
    )
    tv_addons = [addon for addon in selected if _is_tv_stream_addon(addon)]
    kodilog(f"Loaded {len(tv_addons)} selected Nuvio TV addons")
    return tv_addons


def _get_nuvio_addon_pool() -> AddonManager:
    records = _safe_cache_get(NUVIO_USER_ADDONS) or []
    if not isinstance(records, list):
        return AddonManager([])
    return AddonManager(records)


def get_nuvio_addon_by_key(addon_key):
    """Resolve a Nuvio-owned Addon from its instance key or legacy key."""
    return _get_nuvio_addon_pool().get_addon_by_key(addon_key)


def get_nuvio_addon_by_base_url(addon_url):
    """Resolve a Nuvio-owned Addon object from its base URL."""
    for addon in _get_nuvio_addon_pool().addons:
        if addon.url() == addon_url:
            return addon
    return None
