import os
from resources.lib.db.database import get_db
from resources.lib.utils.kodi import ADDON_PATH
from xbmcgui import ListItem
from xbmcplugin import (
    addDirectoryItem,
    endOfDirectory,
    setPluginCategory,
)


def last_titles(plugin, func1, func2, func3):
    setPluginCategory(plugin.handle, f"Last Titles - History")

    list_item = ListItem(label="Clear Titles")
    list_item.setArt(
        {"icon": os.path.join(ADDON_PATH, "resources", "img", "clear.png")}
    )
    addDirectoryItem(plugin.handle, plugin.url_for(func1, type="lth"), list_item)

    for title, data in reversed(get_db().database["jt:lth"].items()):
        formatted_time = data["timestamp"].strftime("%a, %d %b %Y %I:%M %p")
        
        list_item = ListItem(label=f"{title}— {formatted_time}")
        list_item.setArt(
            {"icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png")}
        )
        list_item.setProperty("IsPlayable", "false")

        mode = data["mode"]
        ids = data.get("ids")

        if mode == "tv":
            addDirectoryItem(
                plugin.handle,
                plugin.url_for(
                    func2,
                    ids=ids,
                    mode=mode,
                ),
                list_item,
                isFolder=True,
            )
        else:
            addDirectoryItem(
                plugin.handle,
                plugin.url_for(
                    func3,
                    mode=mode,
                    query=title,
                    ids=ids,
                ),
                list_item,
                isFolder=True,
            )
    endOfDirectory(plugin.handle)
