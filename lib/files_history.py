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
        formatted_time = data["timestamp"].strftime("%a, %d %b %Y %I:%M %p")
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
                data={
                    "title": title,
                    "is_torrent": data.get("is_torrent"),
                    "ids": data.get("ids"),
                    "url": data.get("url"),
                    "info_hash": data.get("info_hash"),
                    "magnet": data.get("magnet"),
                    "tv_data": data.get("tv_data"),
                    "debrid_info": {
                        "file_id": data.get("file_id"),
                        "torrent_id": data.get("torrent_id"),
                        "type": data.get("type"),
                        "is_debrid_pack": data.get("is_debrid_pack"),
                    },
                },
            ),
            list_item,
            False,
        )
    endOfDirectory(ADDON_HANDLE)
