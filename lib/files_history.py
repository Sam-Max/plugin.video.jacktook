import os
from lib.db.database import get_db
from lib.utils.kodi import ADDON_PATH, url_for, url_for_path
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

    for title, data in reversed(get_db().database["jt:lfh"].items()):
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
                ids=data.get("ids"),
                tv_data=data.get("tv_data"),
                url=data.get("url"),
                is_debrid=data.get("is_debrid"),
                is_torrent=data.get("is_torrent"),
                magnet=data.get("magnet"),
            ),
            list_item,
            False,
        )
    endOfDirectory(plugin.handle)
