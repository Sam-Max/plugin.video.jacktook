import json
import os
from lib.db.pickle_db import PickleDatabase
from lib.utils.general.utils import parse_time, set_pluging_category
from lib.utils.kodi.utils import ADDON_HANDLE, ADDON_PATH, build_url, translation

from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem, endOfDirectory


pickle_db = PickleDatabase()


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

    all_items = list(reversed(pickle_db.get_key("jt:lfh").items()))

    items = sorted(all_items, key=parse_time, reverse=True)

    for title, data in items:
        formatted_time = data["timestamp"]
        tv_data = data.get("tv_data", {})
        if tv_data:
            season = tv_data.get("season")
            episode = tv_data.get("episode")
            name = tv_data.get("name", "")
            label = f"{title} S{season:02d}E{episode:02d} - {name} — {formatted_time}"
        else:
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
                data=json.dumps(data),
            ),
            list_item,
            False,
        )
    endOfDirectory(ADDON_HANDLE)
