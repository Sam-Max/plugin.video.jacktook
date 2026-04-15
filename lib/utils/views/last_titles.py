import json
import os

from lib.clients.tmdb.utils.utils import tmdb_get
from lib.db.pickle_db import PickleDatabase
from lib.jacktook.utils import kodilog
from lib.utils.general.utils import parse_time, set_media_infoTag, set_pluging_category
from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    ADDON_PATH,
    add_directory_items_batch,
    apply_section_view,
    build_url,
    container_refresh,
    end_of_directory,
    make_list_item,
    translation,
)




pickle_db = PickleDatabase()


def delete_last_title_entry(params):
    pickle_db.delete_item(key="jt:lth", subkey=params.get("title"))
    container_refresh()


def show_last_titles(params):
    if params is None:
        params = {}

    set_pluging_category(translation(90070))

    per_page = 10
    page = int(params.get("page", 1))

    all_items = list(reversed(pickle_db.get_key("jt:lth").items()))
    total = len(all_items)

    start = (page - 1) * per_page
    end = start + per_page
    items = all_items[start:end]

    items = sorted(items, key=parse_time, reverse=True)

    # Add "Clear Titles" button
    directory_items = []

    list_item = make_list_item(label="Clear Titles")
    list_item.setArt(
        {"icon": os.path.join(ADDON_PATH, "resources", "img", "clear.png")}
    )
    directory_items.append((build_url("clear_history", type="lth"), list_item, True))

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

        list_item = make_list_item(label=f"{title} — {formatted_time}")
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
            directory_items.append(
                (build_url("show_seasons_details", ids=ids, mode=mode), list_item, True)
            )
        elif mode == "movies":
            list_item.setProperty("IsPlayable", "true")
            directory_items.append(
                (build_url("search", mode=mode, query=title, ids=ids), list_item, False)
            )
        elif mode == "tg_latest":
            directory_items.append(
                (
                    build_url(
                        "list_jackgram_title_sources", data=json.dumps(data.get("tg_data"))
                    ),
                    list_item,
                    True,
                )
            )

    # "Next Page"
    if end < total:
        list_item = make_list_item(label=f"Next Page")
        list_item.setArt(
            {"icon": os.path.join(ADDON_PATH, "resources", "img", "nextpage.png")}
        )
        directory_items.append((build_url("titles_history", page=page + 1), list_item, True))

    add_directory_items_batch(directory_items)

    end_of_directory()
    apply_section_view("view.history")
