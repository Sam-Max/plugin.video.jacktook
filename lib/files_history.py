import os
from lib.db.main_db import main_db
from lib.utils.kodi_utils import ADDON_HANDLE, ADDON_PATH, build_url
from xbmcgui import ListItem
from xbmcplugin import (
    addDirectoryItem,
    endOfDirectory,
    setPluginCategory,
)


def last_files():
    setPluginCategory(ADDON_HANDLE, f"Last Files - History")

    list_item = ListItem(label="Clear Files")
    list_item.setArt(
        {"icon": os.path.join(ADDON_PATH, "resources", "img", "clear.png")}
    )
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("clear_history", type="lfh"),
        list_item,
    )

    for title, data in reversed(main_db.database["jt:lfh"].items()):
        formatted_time = data["timestamp"]
        label = f"{title}—{formatted_time}"
        list_item = ListItem(label=label)
        list_item.setArt(
            {"icon": os.path.join(ADDON_PATH, "resources", "img", "magnet.png")}
        )
        list_item.setProperty("IsPlayable", "true")

        addDirectoryItem(
            ADDON_HANDLE,
            build_url(
                "play_torrent",
                data=data,
            ),
            list_item,
            False,
        )
    endOfDirectory(ADDON_HANDLE)
