# -*- coding: utf-8 -*-
import os
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

    for title, data in items:
        ids = data.get("ids", {})

        # Fetch details for rich metadata
        if mode == "tv":
            details = tmdb_get("tv_details", ids.get("tmdb_id"))
        else:
            details = tmdb_get("movie_details", ids.get("tmdb_id"))

        if not details:
            continue

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
