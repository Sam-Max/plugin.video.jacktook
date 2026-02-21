from typing import List, Callable, Optional
import requests
import concurrent.futures
from datetime import timedelta
from lib.api.stremio.addon_manager import Addon, AddonManager
from lib.api.stremio.api_client import Stremio
from lib.db.cached import cache
from lib.utils.kodi.utils import get_setting, kodilog
from lib.clients.stremio.constants import (
    STREMIO_ADDONS_KEY,
    STREMIO_ADDONS_CATALOGS_KEY,
    STREMIO_TV_ADDONS_KEY,
    STREMIO_USER_ADDONS,
)


def merge_addons_lists(*lists):
    seen = set()
    merged = []

    for addon_source in lists:
        if isinstance(addon_source, dict):
            addons = addon_source.get("addons", [])
        else:
            addons = addon_source
        for addon in addons:
            key = (
                addon.get("transportUrl")
                or addon.get("manifest", {}).get("id")
                or addon.get("id")
            )
            if key and key not in seen:
                seen.add(key)
                merged.append(addon)
    return merged


def get_addons():
    all_user_addons = cache.get(STREMIO_USER_ADDONS) or []
    custom_addons = [a for a in all_user_addons if a.get("transportName") == "custom"]

    logged_in = get_setting("stremio_loggedin")
    if logged_in:
        stremio = Stremio()
        try:
            email = get_setting("stremio_email")
            password = get_setting("stremio_pass")
            if email and password:
                stremio.login(email, password)
                user_addons = stremio.get_my_addons() or []
            else:
                kodilog("Stremio credentials missing, cannot fetch user addons.")
                user_addons = []
        except Exception as e:
            kodilog(f"Failed to fetch user addons: {e}")
            user_addons = []
        merged_addons = merge_addons_lists(custom_addons, user_addons)
    else:
        community_addons = cache.get("stremio_community_addons")
        if community_addons is None:
            stremio = Stremio()
            try:
                community_addons = stremio.get_community_addons()
            except Exception as e:
                kodilog(f"Failed to fetch community addons: {e}")
                community_addons = []
            cache.set("stremio_community_addons", community_addons, timedelta(hours=12))
        merged_addons = merge_addons_lists(custom_addons, community_addons)

    kodilog(f"Loaded {len(merged_addons)} addons from catalog")
    return AddonManager(merged_addons)


def get_selected_stream_addons() -> List[Addon]:
    catalog = get_addons()
    selected_ids = cache.get(STREMIO_ADDONS_KEY)
    if not selected_ids:
        return []
    selected_ids_list = selected_ids.split(",")
    return [addon for addon in catalog.addons if addon.key() in selected_ids_list]


def get_selected_catalogs_addons() -> List[Addon]:
    catalog = get_addons()
    selected_ids = cache.get(STREMIO_ADDONS_CATALOGS_KEY)
    if not selected_ids:
        return []
    selected_ids_list = selected_ids.split(",")
    return [addon for addon in catalog.addons if addon.key() in selected_ids_list]


def get_selected_tv_addons() -> List[Addon]:
    catalog = get_addons()
    selected_ids = cache.get(STREMIO_TV_ADDONS_KEY)
    if not selected_ids:
        return []
    selected_ids_list = selected_ids.split(",")
    return [addon for addon in catalog.addons if addon.key() in selected_ids_list]


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
