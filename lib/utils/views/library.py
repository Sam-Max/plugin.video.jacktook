# -*- coding: utf-8 -*-
import os
from lib.db.cached import cache
from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem, endOfDirectory, setContent
from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    ADDON_PATH,
    build_url,
    translation,
)
from lib.db.pickle_db import PickleDatabase
from lib.utils.views.last_titles import parse_time
from lib.clients.tmdb.utils.utils import tmdb_get
from lib.utils.general.utils import (
    set_media_infoTag,
    remove_from_library,
    set_pluging_category,
)
from lib.jacktook.utils import kodilog
from lib.utils.kodi.utils import end_of_directory


def _library_cache_key(mode):
    return "library_view|{}".format(mode)


def _get_library_entries(items, mode):
    cached_entries = cache.get(_library_cache_key(mode))
    if cached_entries:
        return cached_entries

    entries = []
    details_path = "tv_details" if mode == "tv" else "movie_details"

    for title, data in items:
        ids = data.get("ids", {})
        details = tmdb_get(details_path, ids.get("tmdb_id"))
        if details:
            entries.append((title, data, details))

    cache.set(_library_cache_key(mode), entries)
    return entries


def show_library_items(mode="tv"):
    if mode == "tv":
        category = translation(90202)  # My Shows
    else:
        category = translation(90203)  # My Movies

    set_pluging_category(category)
    setContent(ADDON_HANDLE, mode)  # "tv" or "movies"

    all_items = list(reversed(PickleDatabase().get_key("jt:lib").items()))

    # Filter by mode
    items = []
    for title, data in all_items:
        item_mode = data.get("mode")
        if mode == "tv" and item_mode == "tv":
            items.append((title, data))
        elif mode == "movies" and item_mode in ["movie", "movies"]:
            items.append((title, data))

    items = sorted(items, key=parse_time, reverse=True)

    for title, data, details in _get_library_entries(items, mode):
        ids = data.get("ids", {})

        list_item = ListItem(label=f"{title}")
        set_media_infoTag(list_item, data=details, mode=mode)

        # Icon fallback
        list_item.setArt(
            {"icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png")}
        )

        remove_url = build_url("remove_from_library", title=title)

        list_item.addContextMenuItems(
            [
                (
                    translation(90204),
                    f"RunPlugin({remove_url})",
                )  # "Remove from Library" (Need ID)
            ]
        )

        if mode == "tv":
            addDirectoryItem(
                ADDON_HANDLE,
                build_url("show_seasons_details", ids=ids, mode=mode),
                list_item,
                isFolder=True,
            )
        else:  # movies
            list_item.setProperty("IsPlayable", "true")
            addDirectoryItem(
                ADDON_HANDLE,
                build_url("search", mode=mode, query=title, ids=ids),
                list_item,
                isFolder=False,
            )

    end_of_directory(cache=False)


def remove_library_item(params):
    title = params.get("title")
    if title:
        remove_from_library(title)
        from xbmc import executebuiltin

        executebuiltin("Container.Refresh")
