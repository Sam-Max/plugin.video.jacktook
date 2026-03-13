from datetime import timedelta
import os

from xbmcgui import Dialog, ListItem
from xbmcplugin import addDirectoryItem, endOfDirectory

from lib.db.cached import cache
from lib.utils.general.items_menus import history_menu_items, library_menu_items
from lib.utils.general.utils import build_list_item, clear_history_by_type, set_pluging_category
from lib.utils.kodi.settings import get_cache_expiration
from lib.utils.kodi.utils import (
    ADDON_PATH,
    ADDON_HANDLE,
    build_url,
    container_update,
    end_of_directory,
    kodi_play_media,
    notification,
    show_keyboard,
    translation,
)
from lib.utils.views.last_files import show_last_files
from lib.utils.views.last_titles import show_last_titles
from lib.utils.views.weekly_calendar import show_weekly_calendar


def _render_menu(items, cache_listing=True):
    for item in items:
        if "condition" in item and not item["condition"]():
            continue

        name = item["name"]
        if isinstance(name, int):
            name = translation(name)

        list_item = build_list_item(name, item["icon"])
        params = item.get("params", {})
        url = build_url(item["action"], **params)
        addDirectoryItem(ADDON_HANDLE, url, list_item, isFolder=True)

    end_of_directory(cache=cache_listing)


def history_menu(params):
    set_pluging_category(translation(90017))
    _render_menu(history_menu_items)


def library_menu(params):
    set_pluging_category(translation(90201))
    _render_menu(library_menu_items)


def continue_watching_menu(params):
    from lib.utils.views.continue_watching import show_continue_watching

    show_continue_watching()


def remove_from_continue_watching(params):
    from lib.utils.views.continue_watching import remove_continue_watching_item

    remove_continue_watching_item(params)


def library_shows(params):
    from lib.utils.views.library import show_library_items

    show_library_items(mode="tv")


def library_movies(params):
    from lib.utils.views.library import show_library_items

    show_library_items(mode="movies")


def library_calendar(params):
    show_weekly_calendar(library=True)


def remove_from_library(params):
    from lib.utils.views.library import remove_library_item

    remove_library_item(params)


def add_to_library(params):
    from lib.utils.general.utils import add_to_library as add_lib
    import json

    data = params.get("data")
    if data:
        add_lib(json.loads(data))

    Dialog().notification("Jacktook", translation(90205))


def search_direct(params):
    set_pluging_category(translation(90011))
    mode = params.get("mode")
    query = params.get("query", "")
    is_clear = params.get("is_clear", False)
    is_keyboard = params.get("is_keyboard", True)
    update_listing = params.get("update_listing", False)
    rename = params.get("rename", False)

    if is_clear:
        cache.clear_list(key=mode)
        is_keyboard = False

    if rename or is_clear:
        update_listing = True

    if is_keyboard:
        text = show_keyboard(id=30243, default=query)
        if text:
            cache.add_to_list(
                key=mode,
                item=(mode, text),
                expires=timedelta(hours=get_cache_expiration()),
            )

    list_item = ListItem(label=translation(90006))
    list_item.setArt({"icon": os.path.join(ADDON_PATH, "resources", "img", "search.png")})
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("search_direct", mode=mode),
        list_item,
        isFolder=True,
    )

    for item_mode, text in cache.get_list(key=mode):
        list_item = ListItem(label=f"[I]{text}[/I]")
        list_item.setArt(
            {"icon": os.path.join(ADDON_PATH, "resources", "img", "search.png")}
        )
        list_item.setProperty("IsPlayable", "true")
        list_item.addContextMenuItems(
            [
                (
                    translation(90049),
                    kodi_play_media(
                        name="search",
                        mode=item_mode,
                        query=text,
                        rescrape=True,
                        direct=True,
                    ),
                ),
                (
                    "Modify Search",
                    container_update(
                        "search_direct",
                        mode=item_mode,
                        query=text,
                        rename=True,
                    ),
                ),
            ]
        )
        addDirectoryItem(
            ADDON_HANDLE,
            build_url("search", mode=item_mode, query=text, direct=True),
            list_item,
            isFolder=False,
        )

    list_item = ListItem(label="Clear Searches")
    list_item.setArt({"icon": os.path.join(ADDON_PATH, "resources", "img", "clear.png")})
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("search_direct", mode=mode, is_clear=True),
        list_item,
        isFolder=True,
    )
    endOfDirectory(ADDON_HANDLE, updateListing=update_listing)


def clear_history(params):
    clear_history_by_type(type=params.get("type"))
    notification(translation(90114))


def clear_search_history(params):
    import xbmc

    cache.clear_list(key="multi")
    cache.clear_list(key="direct")
    notification(translation(90114))
    xbmc.executebuiltin("Container.Refresh")


def files_history(params):
    show_last_files()


def titles_history(params):
    show_last_titles(params)


def titles_calendar(params):
    show_weekly_calendar()
