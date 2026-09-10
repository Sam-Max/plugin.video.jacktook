"""Offline, database-only Nuvio library view.

"My Movies" and "My Shows" render exclusively from the per-profile SQLite
mirror written by ``NuvioSyncService``. The view performs no network I/O and
never blocks on sync; item routing uses only the stored ``tmdb_id``.
"""

from xbmcplugin import setContent

from lib.api.nuvio import NuvioClient, is_nuvio_progress_sync_enabled
from lib.api.nuvio_store import NuvioStore
from lib.utils.general.utils import set_media_infoTag, set_pluging_category
from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    add_directory_items_batch,
    apply_section_view,
    build_url,
    end_of_directory,
    get_setting,
    kodilog,
    make_list_item,
    notification,
    translation,
)

EMPTY_LIBRARY_NOTIFICATION = 91034

# Maps the menu/params mode to (mirror content_type, Kodi content type, string id).
_MODE_CONTENT = {
    "movies": ("movie", "movies", 91032),
    "tv": ("series", "tvshows", 91033),
}


def _selected_profile_id():
    """Resolve the selected Nuvio profile from settings without a client."""
    return NuvioClient._profile_index(get_setting("nuvio_profile_id"))


def _load_items(profile_id, content_type):
    """Read the mirror rows for the profile; never raises into the UI."""
    if profile_id is None:
        return []
    try:
        store = NuvioStore()
        try:
            return store.list_items(profile_id, content_type)
        finally:
            store.close()
    except Exception as error:
        kodilog(f"[NUVIO] library view read failed ({type(error).__name__})")
        return []


def has_nuvio_library_items() -> bool:
    """True when sync is enabled and the selected profile mirror has rows."""
    if not is_nuvio_progress_sync_enabled():
        return False
    profile_id = _selected_profile_id()
    if profile_id is None:
        return False
    try:
        store = NuvioStore()
        try:
            return store.count(profile_id) > 0
        finally:
            store.close()
    except Exception as error:
        kodilog(f"[NUVIO] library mirror count failed ({type(error).__name__})")
        return False


def _details_from_item(item):
    """Build a Kodi info dict from stored mirror fields only (no network)."""
    title = item.get("title") or ""
    background = item.get("background") or ""
    return {
        "title": title,
        "name": title,
        "original_title": title,
        "original_name": title,
        "overview": item.get("description") or "",
        "poster": item.get("poster") or "",
        "fanart": background,
        "banner": background,
        "landscape": background,
        "id": item.get("tmdb_id"),
        "genres": item.get("genres") or [],
    }


def _item_url(mode, tmdb_id, label):
    if mode == "tv":
        return build_url(
            "show_seasons_details",
            ids={"tmdb_id": str(tmdb_id)},
            mode="tv",
        )
    return build_url(
        "search",
        mode="movies",
        query=label,
        ids={"tmdb_id": str(tmdb_id)},
    )


def show_nuvio_library(params):
    params = params or {}
    mode = params.get("mode", "movies")
    if mode not in _MODE_CONTENT:
        mode = "movies"
    content_type, kodi_content_type, category_id = _MODE_CONTENT[mode]

    set_pluging_category(translation(category_id))
    setContent(ADDON_HANDLE, kodi_content_type)

    items = _load_items(_selected_profile_id(), content_type)

    directory_items = []
    for item in items:
        tmdb_id = item.get("tmdb_id")
        if tmdb_id in (None, ""):
            continue
        label = item.get("title") or f"TMDB {tmdb_id}"
        list_item = make_list_item(label=label)
        set_media_infoTag(
            list_item,
            data=_details_from_item(item),
            mode="tv" if mode == "tv" else "movies",
        )
        content_id = item.get("content_id")
        content_type = item.get("content_type")
        if content_id and content_type:
            remove_url = build_url(
                "nuvio_remove_from_library",
                content_id=content_id,
                content_type=content_type,
            )
            list_item.addContextMenuItems(
                [
                    (
                        translation(91040),
                        f"RunPlugin({remove_url})",
                    )
                ]
            )
        is_folder = mode == "tv"
        directory_items.append((_item_url(mode, tmdb_id, label), list_item, is_folder))

    add_directory_items_batch(directory_items)
    end_of_directory(cache=False)
    apply_section_view("view.library", content_type=kodi_content_type)

    if not directory_items:
        notification(translation(EMPTY_LIBRARY_NOTIFICATION))
