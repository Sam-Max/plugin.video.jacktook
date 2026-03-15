from typing import List, Callable, Optional
import requests
import concurrent.futures
from urllib.parse import urlsplit, urlunsplit
from lib.api.stremio.addon_manager import Addon, AddonManager
from lib.api.stremio.api_client import Stremio
from lib.db.cached import cache
from lib.utils.kodi.utils import get_setting, kodilog
from lib.clients.stremio.constants import (
    STREMIO_ADDONS_KEY,
    STREMIO_ADDONS_CATALOGS_KEY,
    STREMIO_TV_ADDONS_KEY,
    STREMIO_USER_ADDONS,
    decode_selected_ids,
)


def normalize_transport_url(url):
    if not url:
        return ""

    normalized_url = str(url).strip()
    if normalized_url.startswith("stremio://"):
        normalized_url = normalized_url.replace("stremio://", "https://", 1)

    parts = urlsplit(normalized_url)
    path = parts.path.rstrip("/")
    if path.endswith("/manifest.json"):
        path = path[: -len("/manifest.json")]

    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), path, parts.query, "")
    )


def get_addon_merge_key(addon):
    manifest = addon.get("manifest", {}) if isinstance(addon, dict) else {}
    addon_id = (manifest.get("id") or addon.get("id") or "").strip().lower()
    normalized_url = normalize_transport_url(addon.get("transportUrl"))

    if addon_id:
        return addon_id
    if normalized_url:
        return normalized_url

    name = (manifest.get("name") or addon.get("name") or "").strip().lower()
    return name


def merge_addons_lists(*lists):
    seen = set()
    merged = []

    for addon_source in lists:
        if isinstance(addon_source, dict):
            addons = addon_source.get("addons", [])
        else:
            addons = addon_source
        for addon in addons:
            key = get_addon_merge_key(addon)
            if key and key not in seen:
                seen.add(key)
                merged.append(addon)
    return merged


def get_addons():
    all_user_addons = cache.get(STREMIO_USER_ADDONS) or []
    custom_addons = [a for a in all_user_addons if a.get("transportName") == "custom"]
    cached_account_addons = [
        a for a in all_user_addons if a.get("transportName") != "custom"
    ]
    user_addons = list(cached_account_addons)

    logged_in = get_setting("stremio_loggedin")
    if logged_in:
        stremio = Stremio()
        try:
            email = get_setting("stremio_email")
            password = get_setting("stremio_pass")
            if email and password:
                stremio.login(email, password)
                live_user_addons = stremio.get_my_addons() or []
                user_addons = merge_addons_lists(live_user_addons, cached_account_addons)
            else:
                kodilog("Stremio credentials missing, cannot fetch user addons.")
        except Exception as e:
            kodilog(f"Failed to fetch user addons: {e}")
    merged_addons = merge_addons_lists(custom_addons, user_addons)

    kodilog(f"Loaded {len(merged_addons)} addons from catalog")
    return AddonManager(merged_addons)


def get_selected_stream_addons() -> List[Addon]:
    catalog = get_addons()
    selected_ids_list = decode_selected_ids(cache.get(STREMIO_ADDONS_KEY))
    if not selected_ids_list:
        return []
    return [
        addon
        for addon in catalog.addons
        if addon.key() in selected_ids_list or addon.manifest.id in selected_ids_list
    ]


def get_selected_catalogs_addons() -> List[Addon]:
    catalog = get_addons()
    selected_ids_list = decode_selected_ids(cache.get(STREMIO_ADDONS_CATALOGS_KEY))
    if not selected_ids_list:
        return []
    return [
        addon
        for addon in catalog.addons
        if addon.key() in selected_ids_list or addon.manifest.id in selected_ids_list
    ]


def get_selected_tv_addons() -> List[Addon]:
    catalog = get_addons()
    selected_ids_list = decode_selected_ids(cache.get(STREMIO_TV_ADDONS_KEY))
    if not selected_ids_list:
        return []
    return [
        addon
        for addon in catalog.addons
        if addon.key() in selected_ids_list or addon.manifest.id in selected_ids_list
    ]


def get_addon_by_base_url(addon_url):
    """Resolve an Addon object from its base URL."""
    catalog = get_addons()
    for addon in catalog.addons:
        if addon.url() == addon_url:
            return addon
    return None


def ping_addons(
    addons: List[Addon], progress_callback: Optional[Callable[[int, int], None]] = None
) -> List[Addon]:
    reachable_addons = []
    total = len(addons)
    completed = 0

    def check_addon(addon):
        try:
            url = addon.transport_url
            if not url.endswith("/manifest.json"):
                if not url.endswith("/"):
                    url += "/"
                url += "manifest.json"
            requests.get(url, timeout=5)
            return addon
        except Exception:
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(check_addon, addon): addon for addon in addons}
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                reachable_addons.append(result)
            completed += 1
            if progress_callback:
                progress_callback(completed, total)

    return reachable_addons
