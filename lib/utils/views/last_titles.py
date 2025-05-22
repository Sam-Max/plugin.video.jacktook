import json
import os
from lib.db.main import main_db
from lib.utils.kodi.utils import ADDON_HANDLE, ADDON_PATH, build_url
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

        list_item = ListItem(label=f"{title}— {formatted_time}")
        list_item.setArt(
            {"icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png")}
        )

        mode = data["mode"]
        ids = data.get("ids")

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
                    "get_telegram_latest_files",
                    data=json.dumps(data.get("tg_data")),
                ),
                list_item,
                isFolder=True,
            )

    endOfDirectory(ADDON_HANDLE)