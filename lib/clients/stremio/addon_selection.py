from collections import Counter
from datetime import timedelta

import requests
import xbmcgui

from lib.api.stremio.addon_manager import build_addon_instance_key
from lib.clients.stremio.constants import (
    STREMIO_ADDON_ALIASES_KEY,
    STREMIO_ADDONS_CATALOGS_KEY,
    STREMIO_ADDONS_KEY,
    STREMIO_CATALOG_ALIASES_KEY,
    STREMIO_TV_ADDONS_KEY,
    STREMIO_USER_ADDONS,
    decode_selected_ids,
    encode_selected_ids,
    excluded_addons,
)
from lib.clients.stremio.helpers import (
    clear_addon_alias,
    clear_catalog_alias,
    get_addon_alias,
    get_addon_display_name,
    get_addon_merge_key,
    get_addons,
    get_catalog_alias,
    get_catalog_display_name,
    ping_addons,
    set_addon_alias,
    set_catalog_alias,
)
from lib.db.cached import cache
from lib.utils.general.utils import USER_AGENT_HEADER
from lib.utils.kodi.settings import get_int_setting
from lib.utils.kodi.utils import (
    ADDON,
    get_setting,
    get_setting_fresh,
    kodilog,
    set_setting,
    translation,
)


def _ping_addons_with_progress(addons):
    """Ping addons and show progress dialog."""
    total_addons = len(addons)

    progress_dialog = xbmcgui.DialogProgress()
    progress_dialog.create(translation(90153), translation(90607))

    def update_progress(completed, total):
        percent = int((completed / total) * 100)
        progress_dialog.update(percent, translation(90608) % (completed, total))

    reachable_addons = ping_addons(addons, progress_callback=update_progress)
    progress_dialog.close()

    # Show summary
    reachable_count = len(reachable_addons)
    unreachable_count = total_addons - reachable_count

    dialog = xbmcgui.Dialog()
    dialog.ok(
        translation(90609),
        translation(90610) % (reachable_count, unreachable_count),
    )

    return reachable_addons


def _build_addon_options(addons):
    """Build list items for addon multiselect with deduplication."""
    name_counts = Counter(get_addon_display_name(addon) for addon in addons)
    options = []

    for addon in addons:
        name = get_addon_display_name(addon)
        if name_counts[name] > 1:
            label = addon.label().replace(addon.manifest.name, name, 1)
        else:
            label = name

        option = xbmcgui.ListItem(label=label, label2=f"{addon.manifest.description}")

        logo = addon.manifest.logo
        if not logo or logo.endswith(".svg"):
            logo = "DefaultAddon.png"

        option.setArt({"icon": logo})
        options.append(option)

    return options


def _select_addon(title, addons):
    if not addons:
        _show_no_addons_dialog()
        return None

    options = _build_addon_options(addons)
    selected = xbmcgui.Dialog().select(title, options, useDetails=True)
    if selected < 0:
        return None
    return addons[selected]


def _get_aliasable_addons():
    addon_manager = get_addons()
    return _deduplicate_addons(
        [addon for addon in addon_manager.addons if addon.manifest.id != "org.stremio.local"]
    )


def _clear_aliases_for_addon_keys(addon_keys):
    addon_aliases = cache.get(STREMIO_ADDON_ALIASES_KEY) or {}
    if isinstance(addon_aliases, dict):
        addon_aliases = {k: v for k, v in addon_aliases.items() if k not in addon_keys}
        cache.set(STREMIO_ADDON_ALIASES_KEY, addon_aliases, timedelta(days=365 * 20))

    catalog_aliases = cache.get(STREMIO_CATALOG_ALIASES_KEY) or {}
    if isinstance(catalog_aliases, dict):
        catalog_aliases = {
            k: v
            for k, v in catalog_aliases.items()
            if not any(k == addon_key or k.startswith(f"{addon_key}|") for addon_key in addon_keys)
        }
        cache.set(STREMIO_CATALOG_ALIASES_KEY, catalog_aliases, timedelta(days=365 * 20))


def _should_clear_existing_alias():
    return xbmcgui.Dialog().yesno(
        translation(90821),
        translation(90831),
        nolabel=translation(90829),
        yeslabel=translation(90830),
    )


def _show_addon_multiselect(title, addons, selected_ids):
    """Show multiselect dialog and return selected addon keys."""
    options = _build_addon_options(addons)

    dialog = xbmcgui.Dialog()
    selected_ids_list = decode_selected_ids(selected_ids)
    addon_ids = Counter(addon.manifest.id for addon in addons)
    selected_addon_ids = [
        addons.index(addon)
        for addon in addons
        if addon.key() in selected_ids_list
        or (addon.manifest.id in selected_ids_list and addon_ids[addon.manifest.id] == 1)
    ]

    selected_indexes = dialog.multiselect(
        title, options, preselect=selected_addon_ids, useDetails=True
    )

    if selected_indexes is None:
        return None

    return [addons[index].key() for index in selected_indexes]


def _show_no_addons_dialog():
    xbmcgui.Dialog().ok(
        translation(90331),
        translation(90332),
    )


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
        and (not addon.manifest.isConfigurationRequired() or addon.transport_name == "custom")
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
    options = [translation(90333), translation(90334), translation(90335)]
    selection = dialog.select(translation(90611), options)

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

    if not addons:
        _show_no_addons_dialog()
        return

    settings = ADDON.getSettings()
    stremio_email = settings.getString("stremio_email")
    title = stremio_email or translation(90333)

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
            elif res.name == "stream" and ("tv" in res.types or "channel" in res.types):
                is_tv = True
                break
        if not is_tv:
            filtered_addons.append(addon)
    addons = filtered_addons

    if check_availability:
        addons = _ping_addons_with_progress(addons)

    if not addons:
        _show_no_addons_dialog()
        return

    settings = ADDON.getSettings()
    stremio_email = settings.getString("stremio_email")
    title = stremio_email or translation(90334)

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
            elif resource.name == "stream" and (
                "tv" in resource.types or "channel" in resource.types
            ):
                addons.append(addon)
                break

    addons = _deduplicate_addons(addons)
    addons = _filter_excluded_addons(addons)

    if check_availability:
        addons = _ping_addons_with_progress(addons)

    addons = list(reversed(addons))

    if not addons:
        _show_no_addons_dialog()
        return

    settings = ADDON.getSettings()
    stremio_email = settings.getString("stremio_email")
    title = stremio_email or translation(90335)

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
    url = dialog.input(translation(90523), type=xbmcgui.INPUT_ALPHANUM)
    if not url:
        dialog.ok(translation(90522), translation(90524))
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
        dialog.ok(translation(90522), translation(90525) % e)
        return

    try:
        id_ = manifest.get("id") or manifest.get("name")
        if not id_:
            dialog.ok(translation(90522), translation(90526))
            return
        addon_key = build_addon_instance_key({"manifest": manifest, "transportUrl": response.url})

        resources = manifest.get("resources", [])
        # Normalize resources to list of dicts or strings
        if isinstance(resources, (dict, str)):
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
                    # For string resource, rely on top-level types.
                    if "movie" in types or "series" in types:
                        # Checking for 'tt' prefix would be safer, but strings do not expose it.
                        is_stream = True
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
            selected_catalog_keys = decode_selected_ids(cache.get(STREMIO_ADDONS_CATALOGS_KEY))
            if addon_key not in selected_catalog_keys:
                selected_catalog_keys.append(addon_key)
                cache.set(
                    STREMIO_ADDONS_CATALOGS_KEY,
                    encode_selected_ids(selected_catalog_keys),
                    timedelta(days=365 * 20),
                )

        # Always add custom addon to user addons catalog
        user_addons = list(cache.get(STREMIO_USER_ADDONS) or [])

        custom_addon = {
            "manifest": manifest,
            "transportUrl": response.url,
            "transportName": "custom",
        }
        custom_merge_key = get_addon_merge_key(custom_addon)
        if not any(get_addon_merge_key(a) == custom_merge_key for a in user_addons):
            user_addons.append(custom_addon)
            cache.set(STREMIO_USER_ADDONS, user_addons, timedelta(days=365 * 20))

            if is_stream or is_catalog or is_tv_stream:
                dialog.ok(translation(90522), translation(90527))
            else:
                dialog.ok(translation(90522), translation(90528))
        else:
            dialog.ok(translation(90522), translation(90529))
    except Exception as e:
        dialog.ok(translation(90522), translation(90530) % e)


def remove_custom_stremio_addon(params=None):
    user_addons = cache.get(STREMIO_USER_ADDONS) or []
    removable_addons = [a for a in user_addons if a.get("transportName") == "custom"]
    if not removable_addons:
        xbmcgui.Dialog().ok(translation(90531), translation(90532))
        return

    options = []
    for addon in removable_addons:
        manifest = addon.get("manifest", {})
        name = manifest.get("name") or manifest.get("id") or addon.get("transportUrl", "Unknown")
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
    selected = dialog.multiselect(translation(90533), options, useDetails=True)
    if not selected:
        return

    # Remove selected addons
    to_remove_keys = set()
    for idx in selected:
        addon = removable_addons[idx]
        addon_key = build_addon_instance_key(addon)
        if addon_key:
            to_remove_keys.add(addon_key)

    # Remove from user_addons
    new_user_addons = [a for a in user_addons if build_addon_instance_key(a) not in to_remove_keys]
    cache.set(STREMIO_USER_ADDONS, new_user_addons, timedelta(days=365 * 20))
    _clear_aliases_for_addon_keys(to_remove_keys)

    # Remove from selected stream/catalogs/tv if present
    for cache_key in [
        STREMIO_ADDONS_KEY,
        STREMIO_ADDONS_CATALOGS_KEY,
        STREMIO_TV_ADDONS_KEY,
    ]:
        selected_keys = decode_selected_ids(cache.get(cache_key))
        if selected_keys:
            selected_keys = [k for k in selected_keys if k not in to_remove_keys]
            cache.set(cache_key, encode_selected_ids(selected_keys), timedelta(days=365 * 20))

    xbmcgui.Dialog().ok(translation(90531), translation(90534))


def rename_stremio_addon(params=None):
    addons = _get_aliasable_addons()
    addon = _select_addon(translation(90819), addons)
    if not addon:
        return

    current_alias = get_addon_alias(addon)
    if current_alias and _should_clear_existing_alias():
        clear_addon_alias(addon)
        xbmcgui.Dialog().ok(translation(90821), translation(90823))
        return

    new_alias = xbmcgui.Dialog().input(
        translation(90820), defaultt=current_alias, type=xbmcgui.INPUT_ALPHANUM
    )
    if (new_alias or "").strip():
        set_addon_alias(addon, new_alias)
        xbmcgui.Dialog().ok(translation(90821), translation(90822))


def rename_stremio_catalog(params=None):
    addons = [addon for addon in _get_aliasable_addons() if addon.manifest.catalogs]
    addon = _select_addon(translation(90824), addons)
    if not addon:
        return

    catalog_options = []
    for catalog in addon.manifest.catalogs:
        item = xbmcgui.ListItem(
            label=get_catalog_display_name(addon, catalog),
            label2=f"{get_addon_display_name(addon)} - {catalog.type}/{catalog.id}",
        )
        item.setArt({"icon": addon.manifest.logo or "DefaultAddon.png"})
        catalog_options.append(item)

    selected = xbmcgui.Dialog().select(translation(90825), catalog_options, useDetails=True)
    if selected < 0:
        return

    catalog = addon.manifest.catalogs[selected]
    current_alias = get_catalog_alias(addon, catalog)
    if current_alias and _should_clear_existing_alias():
        clear_catalog_alias(addon, catalog)
        xbmcgui.Dialog().ok(translation(90821), translation(90823))
        return

    new_alias = xbmcgui.Dialog().input(
        translation(90826), defaultt=current_alias, type=xbmcgui.INPUT_ALPHANUM
    )
    if (new_alias or "").strip():
        set_catalog_alias(addon, catalog, new_alias)
        xbmcgui.Dialog().ok(translation(90821), translation(90822))


def stremio_bypass_addons_select(params=None):
    addon_manager = get_addons()
    addons = addon_manager.get_addons_with_resource("stream")
    addons = _filter_stream_addons_by_id_prefix(addons, ["tt", "tmdb"])
    addons = _deduplicate_addons(addons)
    addons = _filter_excluded_addons(addons)
    addons = list(reversed(addons))

    selected_list_str = str(get_setting("stremio_bypass_addon_list", "") or "").strip()
    selected_values = [value.strip() for value in selected_list_str.split(",") if value.strip()]

    selected_ids = []
    for addon in addons:
        if addon.key() in selected_values or addon.manifest.name.lower() in selected_values:
            selected_ids.append(addon.key())

    title = translation(90213)
    selected_addon_keys = _show_addon_multiselect(title, addons, selected_ids)

    if selected_addon_keys is None:
        return

    set_setting("stremio_bypass_addon_list", ",".join(selected_addon_keys))


def stremio_subtitle_addons_select(params=None):
    """Let the user pick which Stremio addons Jacktook queries for subtitles.

    Mirrors :func:`stremio_bypass_addons_select` but targets the
    ``subtitles`` resource (no id-prefix filter) and stores the result in the
    ``stremio_subtitle_addons`` hidden setting as a CSV of addon instance
    keys (one key per addon, e.g. ``"<manifest_id>|<transport_url>"``).
    """
    addon_manager = get_addons()
    addons = addon_manager.get_addons_with_resource("subtitles")
    addons = _deduplicate_addons(addons)
    addons = _filter_excluded_addons(addons)
    addons = list(reversed(addons))

    if not addons:
        xbmcgui.Dialog().ok(
            translation(30953),
            translation(30955),
        )
        return

    selected_list_str = str(get_setting_fresh("stremio_subtitle_addons", "") or "").strip()
    selected_values = [value.strip() for value in selected_list_str.split(",") if value.strip()]

    selected_ids = [
        addon.key()
        for addon in addons
        if addon.key() in selected_values or addon.manifest.name.lower() in selected_values
    ]

    title = translation(30953)
    selected_addon_keys = _show_addon_multiselect(title, addons, selected_ids)

    if selected_addon_keys is None:
        return

    set_setting("stremio_subtitle_addons", ",".join(selected_addon_keys))
