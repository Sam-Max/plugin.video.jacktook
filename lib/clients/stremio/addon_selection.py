import requests
from datetime import timedelta
from collections import Counter
from lib.db.cached import cache
from lib.utils.general.utils import USER_AGENT_HEADER
from lib.utils.kodi.utils import (
    kodilog,
    get_setting,
    set_setting,
    ADDON,
)
from lib.utils.kodi.settings import get_int_setting
from lib.clients.stremio.constants import (
    STREMIO_ADDONS_KEY,
    STREMIO_ADDONS_CATALOGS_KEY,
    STREMIO_TV_ADDONS_KEY,
    STREMIO_USER_ADDONS,
    excluded_addons,
    encode_selected_ids,
    decode_selected_ids,
)
from lib.clients.stremio.helpers import get_addons, ping_addons
import xbmcgui


def _ping_addons_with_progress(addons):
    """Ping addons and show progress dialog."""
    total_addons = len(addons)

    progress_dialog = xbmcgui.DialogProgress()
    progress_dialog.create("Stremio", "Pinging addons for availability...")

    def update_progress(completed, total):
        percent = int((completed / total) * 100)
        progress_dialog.update(percent, f"Pinging addons... {completed}/{total}")

    reachable_addons = ping_addons(addons, progress_callback=update_progress)
    progress_dialog.close()

    # Show summary
    reachable_count = len(reachable_addons)
    unreachable_count = total_addons - reachable_count

    dialog = xbmcgui.Dialog()
    dialog.ok(
        "Ping Results",
        f"Reachable: {reachable_count}\nUnreachable: {unreachable_count}",
    )

    return reachable_addons


def _build_addon_options(addons):
    """Build list items for addon multiselect with deduplication."""
    name_counts = Counter(addon.manifest.name for addon in addons)
    options = []

    for addon in addons:
        name = addon.manifest.name
        if name_counts[name] > 1:
            label = f"{name} ({addon.manifest.id})"
        else:
            label = name

        option = xbmcgui.ListItem(label=label, label2=f"{addon.manifest.description}")

        logo = addon.manifest.logo
        if not logo or logo.endswith(".svg"):
            logo = "DefaultAddon.png"

        option.setArt({"icon": logo})
        options.append(option)

    return options


def _show_addon_multiselect(title, addons, selected_ids):
    """Show multiselect dialog and return selected addon keys."""
    options = _build_addon_options(addons)

    dialog = xbmcgui.Dialog()
    selected_ids_list = decode_selected_ids(selected_ids)
    selected_addon_ids = [
        addons.index(addon)
        for addon in addons
        if addon.key() in selected_ids_list or addon.manifest.id in selected_ids_list
    ]

    selected_indexes = dialog.multiselect(
        title, options, preselect=selected_addon_ids, useDetails=True
    )

    if selected_indexes is None:
        return None

    return [addons[index].key() for index in selected_indexes]


def _deduplicate_addons(addons):
    """Remove duplicate addons by key."""
    seen_keys = set()
    unique_addons = []
    for addon in addons:
        if addon.key() not in seen_keys:
            seen_keys.add(addon.key())
            unique_addons.append(addon)
    return unique_addons


def _filter_excluded_addons(addons):
    """Filter out excluded addons and those requiring configuration."""
    return [
        addon
        for addon in addons
        if addon.manifest.id not in excluded_addons
        and (
            not addon.manifest.isConfigurationRequired()
            or addon.transport_name == "custom"
        )
    ]


def _filter_stream_addons_by_id_prefix(addons, allowed_prefixes):
    normalized_allowed = {
        str(prefix).rstrip(":") for prefix in allowed_prefixes if prefix is not None
    }
    filtered = []

    for addon in addons:
        for resource in addon.manifest.resources:
            if isinstance(resource, str):
                continue
            if resource.name != "stream":
                continue

            resource_prefixes = {
                str(p).rstrip(":") for p in (resource.id_prefixes or []) if p is not None
            }
            if resource_prefixes.intersection(normalized_allowed):
                filtered.append(addon)
                break

    return filtered


def stremio_filtered_selection(params):
    dialog = xbmcgui.Dialog()
    options = ["Stream Addons", "Catalogs", "Live TV Addons"]
    selection = dialog.select("Select Category to Filter", options)

    if selection == 0:
        stremio_toggle_addons(params, check_availability=True)
    elif selection == 1:
        stremio_toggle_catalogs(params, check_availability=True)
    elif selection == 2:
        stremio_toggle_tv_addons(params, check_availability=True)


def stremio_toggle_addons(params, check_availability=False):
    selected_ids = cache.get(STREMIO_ADDONS_KEY) or ""
    addon_manager = get_addons()
    addons = addon_manager.get_addons_with_resource("stream")
    addons = _filter_stream_addons_by_id_prefix(addons, ["tt", "tmdb"])

    addons = _deduplicate_addons(addons)
    addons = _filter_excluded_addons(addons)

    if check_availability:
        addons = _ping_addons_with_progress(addons)

    addons = list(reversed(addons))

    settings = ADDON.getSettings()
    stremio_email = settings.getString("stremio_email")
    title = stremio_email or "Stremio Community Addons List"

    selected_addon_keys = _show_addon_multiselect(title, addons, selected_ids)

    if selected_addon_keys is None:
        return

    cache.set(
        STREMIO_ADDONS_KEY,
        encode_selected_ids(selected_addon_keys),
        timedelta(days=365 * 20),
    )


def stremio_toggle_catalogs(params, check_availability=False):
    selected_ids = cache.get(STREMIO_ADDONS_CATALOGS_KEY) or ""
    addon_manager = get_addons()
    addons = addon_manager.get_addons_with_resource("catalog")

    # Filter out Live TV addons
    filtered_addons = []
    for addon in addons:
        is_tv = False
        for res in addon.manifest.resources:
            if isinstance(res, str):
                if res == "stream" and (
                    "tv" in addon.manifest.types or "channel" in addon.manifest.types
                ):
                    is_tv = True
                    break
            elif res.name == "stream":
                if "tv" in res.types or "channel" in res.types:
                    is_tv = True
                    break
        if not is_tv:
            filtered_addons.append(addon)
    addons = filtered_addons

    if check_availability:
        addons = _ping_addons_with_progress(addons)

    settings = ADDON.getSettings()
    stremio_email = settings.getString("stremio_email")
    title = stremio_email or "Stremio Community Catalogs List"

    selected_addon_keys = _show_addon_multiselect(title, addons, selected_ids)

    if selected_addon_keys is None:
        return

    cache.set(
        STREMIO_ADDONS_CATALOGS_KEY,
        encode_selected_ids(selected_addon_keys),
        timedelta(days=365 * 20),
    )


def stremio_toggle_tv_addons(params, check_availability=False):
    selected_ids = cache.get(STREMIO_TV_ADDONS_KEY) or ""
    addon_manager = get_addons()

    addons = []
    for addon in addon_manager.addons:
        if addon.manifest.id == "org.stremio.local":
            continue
        for resource in addon.manifest.resources:
            # Resource can be str or object
            if isinstance(resource, str):
                if resource == "stream" and (
                    "tv" in addon.manifest.types or "channel" in addon.manifest.types
                ):
                    addons.append(addon)
                    break
            elif resource.name == "stream":
                if "tv" in resource.types or "channel" in resource.types:
                    addons.append(addon)
                    break

    addons = _deduplicate_addons(addons)
    addons = _filter_excluded_addons(addons)

    if check_availability:
        addons = _ping_addons_with_progress(addons)

    addons = list(reversed(addons))

    settings = ADDON.getSettings()
    stremio_email = settings.getString("stremio_email")
    title = stremio_email or "Stremio Live TV Addons"

    selected_addon_keys = _show_addon_multiselect(title, addons, selected_ids)

    if selected_addon_keys is None:
        return

    cache.set(
        STREMIO_TV_ADDONS_KEY,
        encode_selected_ids(selected_addon_keys),
        timedelta(days=365 * 20),
    )


def add_custom_stremio_addon(params):
    dialog = xbmcgui.Dialog()
    url = dialog.input(
        "Enter the custom Stremio addon URL", type=xbmcgui.INPUT_ALPHANUM
    )
    if not url:
        dialog.ok("Custom Addon", "No URL provided.")
        return

    if url.startswith("stremio://"):
        url = url.replace("stremio://", "https://")

    # Try to fetch the manifest from the URL
    try:
        response = requests.get(
            url, headers=USER_AGENT_HEADER, timeout=get_int_setting("stremio_timeout")
        )
        response.raise_for_status()
        manifest = response.json()
    except Exception as e:
        kodilog(f"Failed to fetch custom addon manifest: {e}")
        dialog.ok("Custom Addon", f"Failed to fetch manifest: {e}")
        return

    try:
        id_ = manifest.get("id") or manifest.get("name")
        if not id_:
            dialog.ok("Custom Addon", "Manifest missing 'id' or 'name'.")
            return
        addon_key = f"{id_}|{response.url}"

        resources = manifest.get("resources", [])
        # Normalize resources to list of dicts or strings
        if isinstance(resources, dict):
            resources = [resources]
        elif isinstance(resources, str):
            resources = [resources]

        # Determine capabilities
        is_stream = False
        is_catalog = False
        is_tv_stream = False
        types = manifest.get("types", [])

        for res in resources:
            if isinstance(res, dict):
                res_types = res.get("types", types)
                if res.get("name") == "stream":
                    id_prefixes = res.get("idPrefixes", [])
                    if "tt" in id_prefixes:
                        is_stream = True
                    if "tv" in res_types or "channel" in res_types:
                        is_tv_stream = True

                if res.get("name") == "catalog":
                    is_catalog = True
            elif isinstance(res, str):
                if res == "stream":
                    # For string resource, rely on top-elevel types
                    if "movie" in types or "series" in types:
                        is_stream = True  # Assumption for now, though checking for 'tt' prefix is safer properly but here we just have string
                    if "tv" in types or "channel" in types:
                        is_tv_stream = True
                if res == "catalog":
                    is_catalog = True

        # Add to selected addons if stream
        if is_stream:
            selected_keys = decode_selected_ids(cache.get(STREMIO_ADDONS_KEY))
            if addon_key not in selected_keys:
                selected_keys.append(addon_key)
                cache.set(
                    STREMIO_ADDONS_KEY,
                    encode_selected_ids(selected_keys),
                    timedelta(days=365 * 20),
                )

        # Add to selected TV stream addons
        if is_tv_stream:
            selected_tv_keys = decode_selected_ids(cache.get(STREMIO_TV_ADDONS_KEY))
            if addon_key not in selected_tv_keys:
                selected_tv_keys.append(addon_key)
                cache.set(
                    STREMIO_TV_ADDONS_KEY,
                    encode_selected_ids(selected_tv_keys),
                    timedelta(days=365 * 20),
                )

        # Add to selected catalogs if catalog
        if is_catalog:
            selected_catalog_keys = decode_selected_ids(
                cache.get(STREMIO_ADDONS_CATALOGS_KEY)
            )
            if addon_key not in selected_catalog_keys:
                selected_catalog_keys.append(addon_key)
                cache.set(
                    STREMIO_ADDONS_CATALOGS_KEY,
                    encode_selected_ids(selected_catalog_keys),
                    timedelta(days=365 * 20),
                )

        # Always add custom addon to user addons catalog
        user_addons = cache.get(STREMIO_USER_ADDONS) or []

        custom_addon = {
            "manifest": manifest,
            "transportUrl": response.url,
            "transportName": "custom",
        }
        if not any(
            f"{a.get('manifest', {}).get('id') or a.get('manifest', {}).get('name')}|{a.get('transportUrl')}"
            == addon_key
            for a in user_addons
        ):
            user_addons.append(custom_addon)
            cache.set(STREMIO_USER_ADDONS, user_addons, timedelta(days=365 * 20))

            if is_stream or is_catalog or is_tv_stream:
                dialog.ok("Custom Addon", "Custom Stremio addon added successfully!")
            else:
                dialog.ok(
                    "Custom Addon",
                    "Addon does not provide 'stream' or 'catalog' resources.",
                )
        else:
            dialog.ok("Custom Addon", "This addon is already added to your list.")
    except Exception as e:
        dialog.ok("Custom Addon", f"Failed to add custom addon: {e}")


def remove_custom_stremio_addon(params=None):
    user_addons = cache.get(STREMIO_USER_ADDONS) or []
    removable_addons = [a for a in user_addons if a.get("transportName") == "custom"]
    if not removable_addons:
        xbmcgui.Dialog().ok("Remove Addon", "No custom Stremio addons to remove.")
        return

    options = []
    for addon in removable_addons:
        manifest = addon.get("manifest", {})
        name = (
            manifest.get("name")
            or manifest.get("id")
            or addon.get("transportUrl", "Unknown")
        )
        desc = manifest.get("description", "")
        item = xbmcgui.ListItem(label=name, label2=desc)

        logo = manifest.get("logo")
        transport_url = addon.get("transportUrl")
        if logo and transport_url and not logo.startswith(("http://", "https://")):
            from urllib.parse import urljoin

            logo = urljoin(transport_url, logo)

        if not logo or logo.endswith(".svg"):
            logo = "DefaultAddon.png"
        item.setArt({"icon": logo})
        options.append(item)

    dialog = xbmcgui.Dialog()
    selected = dialog.multiselect("Remove Stremio Addons", options, useDetails=True)
    if not selected:
        return

    # Remove selected addons
    to_remove_keys = set()
    for idx in selected:
        addon = removable_addons[idx]
        manifest = addon.get("manifest", {})
        id_ = manifest.get("id") or manifest.get("name")
        url = addon.get("transportUrl")
        if id_ and url:
            to_remove_keys.add(f"{id_}|{url}")

    # Remove from user_addons
    new_user_addons = [
        a
        for a in user_addons
        if f"{a.get('manifest', {}).get('id') or a.get('manifest', {}).get('name')}|{a.get('transportUrl')}"
        not in to_remove_keys
    ]
    cache.set(STREMIO_USER_ADDONS, new_user_addons, timedelta(days=365 * 20))

    # Remove from selected stream/catalogs/tv if present
    for cache_key in [
        STREMIO_ADDONS_KEY,
        STREMIO_ADDONS_CATALOGS_KEY,
        STREMIO_TV_ADDONS_KEY,
    ]:
        selected_keys = decode_selected_ids(cache.get(cache_key))
        if selected_keys:
            selected_keys = [k for k in selected_keys if k not in to_remove_keys]
            cache.set(
                cache_key, encode_selected_ids(selected_keys), timedelta(days=365 * 20)
            )

    xbmcgui.Dialog().ok("Remove Addon", "Selected addon(s) removed.")


def stremio_bypass_addons_select(params=None):
    addon_manager = get_addons()
    addons = addon_manager.get_addons_with_resource("stream")
    addons = _filter_stream_addons_by_id_prefix(addons, ["tt", "tmdb"])
    addons = _deduplicate_addons(addons)
    addons = _filter_excluded_addons(addons)
    addons = list(reversed(addons))

    selected_list_str = get_setting("stremio_bypass_addon_list").strip()
    selected_names_old = selected_list_str.split(",") if selected_list_str else []

    selected_ids = [
        addon.key()
        for addon in addons
        if addon.manifest.name.lower() in selected_names_old
    ]

    title = "Select Bypassed Addons"
    selected_addon_keys = _show_addon_multiselect(title, addons, selected_ids)

    if selected_addon_keys is None:
        return

    selected_names = []
    for addon in addons:
        if addon.key() in selected_addon_keys:
            selected_names.append(addon.manifest.name.lower())

    set_setting("stremio_bypass_addon_list", ",".join(selected_names))
