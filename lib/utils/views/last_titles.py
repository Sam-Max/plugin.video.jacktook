import json
import os
from lib.api.tmdbv3api.objs.movie import Movie
from lib.api.tmdbv3api.objs.tv import TV
from lib.clients.tmdb.utils import tmdb_get
from lib.db.main import main_db
from lib.utils.general.utils import set_media_infoTag
from lib.utils.kodi.utils import ADDON_HANDLE, ADDON_PATH, build_url, kodilog
from xbmcgui import ListItem
from xbmcplugin import (
    addDirectoryItem,
    endOfDirectory,
    setPluginCategory,
)


def show_last_titles():
    setPluginCategory(ADDON_HANDLE, f"Last Titles - History")

    list_item = ListItem(label="Clear Titles")
    list_item.setArt(
        {"icon": os.path.join(ADDON_PATH, "resources", "img", "clear.png")}
    )

    addDirectoryItem(ADDON_HANDLE, build_url("clear_history", type="lth"), list_item)

    for title, data in reversed(main_db.database["jt:lth"].items()):
        formatted_time = data["timestamp"]
        mode = data["mode"]
        ids = data.get("ids")
        
        if mode == "tv":
            details = tmdb_get("tv_details", ids.get("tmdb_id"))
        else:
            details = tmdb_get("movie_details", ids.get("tmdb_id"))

        list_item = ListItem(label=f"{title}— {formatted_time}")
        set_media_infoTag(list_item, metadata=details, mode=data.get("mode"))
        list_item.setArt(
            {"icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png")}
        )

        if mode == "tv":
            addDirectoryItem(
                ADDON_HANDLE,
                build_url(
                    "tv_seasons_details",
                    ids=ids,
                    mode=mode,
                ),
                list_item,
                isFolder=True,
            )
        elif mode == "movies":
            list_item.setProperty("IsPlayable", "true")
            addDirectoryItem(
                ADDON_HANDLE,
                build_url(
                    "search",
                    mode=mode,
                    query=title,
                    ids=ids,
                ),
                list_item,
                isFolder=False,
            )
        elif mode == "tg_latest":
            addDirectoryItem(
                ADDON_HANDLE,
                build_url(
                    "list_telegram_latest_files",
                    data=json.dumps(data.get("tg_data")),
                ),
                list_item,
                isFolder=True,
            )

    endOfDirectory(ADDON_HANDLE)