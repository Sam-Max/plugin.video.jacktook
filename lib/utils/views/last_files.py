import json
import os
from lib.db.pickle_db import PickleDatabase
from lib.utils.general.utils import (
    format_season_episode,
    parse_time,
    set_pluging_category,
)
from lib.utils.kodi.last_files_actions import add_last_files_context_menu
from lib.utils.kodi.utils import ADDON_HANDLE, ADDON_PATH, apply_section_view, build_url, end_of_directory, translation

from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem


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
            name = tv_data.get("name", "")
            episode_label = format_season_episode(
                tv_data.get("season"), tv_data.get("episode")
            )
            if episode_label:
                label = f"{title} {episode_label} - {name} — {formatted_time}"
            else:
                label = f"{title} - {name} — {formatted_time}"
        else:
            label = f"{title}—{formatted_time}"

        list_item = ListItem(label=label)
        list_item.setArt(
            {"icon": os.path.join(ADDON_PATH, "resources", "img", "magnet.png")}
        )
        list_item.setProperty("IsPlayable", "true")
        list_item.addContextMenuItems(add_last_files_context_menu(data))
        addDirectoryItem(
            ADDON_HANDLE,
            build_url(
                "play_media",
                data=json.dumps(data),
            ),
            list_item,
            False,
        )
    end_of_directory()
    apply_section_view("view.history", fallback="list")
