import os
from lib.db.pickle_db import PickleDatabase
from lib.utils.general.utils import set_pluging_category
from lib.utils.kodi.utils import ADDON_HANDLE, ADDON_PATH, build_url, translation
from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem, endOfDirectory


def show_last_files():
    set_pluging_category(translation(90071))

    list_item = ListItem(label="Clear Files")
    list_item.setArt(
        {"icon": os.path.join(ADDON_PATH, "resources", "img", "clear.png")}
    )
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("clear_history", type="lfh"),
        list_item,
    )

    for title, data in reversed(PickleDatabase().get_key("jt:lfh").items()):
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
