from datetime import datetime
import json
import os

from lib.clients.tmdb.utils.utils import tmdb_get
from lib.db.pickle_db import PickleDatabase
from lib.jacktook.utils import kodilog
from lib.utils.general.utils import parse_time, set_media_infoTag, set_pluging_category
from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    ADDON_PATH,
    build_url,
    container_refresh,
    translation,
)

from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem, endOfDirectory


pickle_db = PickleDatabase()


def delete_last_title_entry(params):
    pickle_db.delete_item(key="jt:lth", subkey=params.get("title"))
    container_refresh()


def show_last_titles(params):
    if params is None:
        params = {}

    set_pluging_category(translation(90070))

    per_page = 20
    page = int(params.get("page", 1))

    all_items = list(reversed(pickle_db.get_key("jt:lth").items()))
    total = len(all_items)

    start = (page - 1) * per_page
    end = start + per_page
    items = all_items[start:end]

    items = sorted(items, key=parse_time, reverse=True)

    # Add "Clear Titles" button
    list_item = ListItem(label="Clear Titles")
    list_item.setArt(
        {"icon": os.path.join(ADDON_PATH, "resources", "img", "clear.png")}
    )
    addDirectoryItem(ADDON_HANDLE, build_url("clear_history", type="lth"), list_item)

    for title, data in items:
        formatted_time = data["timestamp"]
        mode = data["mode"]
        ids = data.get("ids")

        if mode == "tv":
            details = tmdb_get("tv_details", ids.get("tmdb_id"))
        else:
            details = tmdb_get("movie_details", ids.get("tmdb_id"))

        if not details:
            kodilog(f"Failed to get details for {mode} with ID {ids.get('tmdb_id')}")
            continue

        list_item = ListItem(label=f"{title} — {formatted_time}")
        set_media_infoTag(list_item, data=details, mode=mode)
        list_item.setArt(
            {"icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png")}
        )

        list_item.addContextMenuItems(
            [
                (
                    "Delete from history",
                    f'RunPlugin({build_url("delete_last_title_entry", title=title)})',
                )
            ]
        )

        if mode == "tv":
            addDirectoryItem(
                ADDON_HANDLE,
                build_url("tv_seasons_details", ids=ids, mode=mode),
                list_item,
                isFolder=True,
            )
        elif mode == "movies":
            list_item.setProperty("IsPlayable", "true")
            addDirectoryItem(
                ADDON_HANDLE,
                build_url("search", mode=mode, query=title, ids=ids),
                list_item,
                isFolder=False,
            )
        elif mode == "tg_latest":
            addDirectoryItem(
                ADDON_HANDLE,
                build_url(
                    "list_telegram_latest_files", data=json.dumps(data.get("tg_data"))
                ),
                list_item,
                isFolder=True,
            )

    # "Next Page"
    if end < total:
        list_item = ListItem(label=f"Next Page")
        list_item.setArt(
            {"icon": os.path.join(ADDON_PATH, "resources", "img", "nextpage.png")}
        )
        addDirectoryItem(
            ADDON_HANDLE,
            build_url("titles_history", page=page + 1),
            list_item,
            isFolder=True,
        )

    endOfDirectory(ADDON_HANDLE)
