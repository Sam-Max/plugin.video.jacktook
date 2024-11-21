import os
from lib.db.main_db import main_db
from lib.utils.kodi_utils import ADDON_PATH, url_for, url_for_path
from xbmcgui import ListItem
from xbmcplugin import (
    addDirectoryItem,
    endOfDirectory,
    setPluginCategory,
)


def last_files(plugin):
    setPluginCategory(plugin.handle, f"Last Files - History")

    list_item = ListItem(label="Clear Files")
    list_item.setArt(
        {"icon": os.path.join(ADDON_PATH, "resources", "img", "clear.png")}
    )
    addDirectoryItem(
        plugin.handle,
        url_for_path(name="history/clear", path="lfh"),
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
            plugin.handle,
            url_for(
                name="play_torrent",
                title=title,
                is_torrent=data.get("is_torrent"),
                data={
                    "ids": data.get("ids"),
                    "url": data.get("url"),
                    "info_hash": data.get("info_hash"),
                    "magnet": data.get("magnet"),
                    "tv_data": data.get("tv_data"),
                    "debrid_info": {
                        "file_id": data.get("file_id"),
                        "torrent_id": data.get("torrent_id"),
                        "debrid_type": data.get("debrid_type"),
                        "is_debrid_pack": data.get("is_debrid_pack"),
                    },
                },
            ),
            list_item,
            False,
        )
    endOfDirectory(plugin.handle)
