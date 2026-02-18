# -*- coding: utf-8 -*-
from lib.jacktook.utils import kodilog
import json
import os
from xbmc import executebuiltin
from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem, endOfDirectory, setContent
from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    ADDON_PATH,
    build_url,
    translation,
)
from lib.db.pickle_db import PickleDatabase
from lib.utils.general.utils import set_pluging_category
from lib.utils.views.last_files import add_last_files_context_menu, parse_time
from lib.utils.kodi.utils import end_of_directory


def has_continue_watching_items():
    all_items = PickleDatabase().get_key("jt:lfh").items()
    for title, data in all_items:
        progress = float(data.get("progress", 0))
        if 5 < progress < 90:
            return True
    return False


def remove_continue_watching_item(params):
    title = params.get("title")
    if title:
        PickleDatabase().delete_item(key="jt:lfh", subkey=title)
        executebuiltin("Container.Refresh")


def show_continue_watching():
    set_pluging_category(translation(90200))
    setContent(ADDON_HANDLE, "videos")

    all_items = list(reversed(PickleDatabase().get_key("jt:lfh").items()))
    items = sorted(all_items, key=parse_time, reverse=True)

    count = 0
    for title, data in items:
        # Check progress
        progress = float(data.get("progress", 0))
        if progress <= 5 or progress >= 90:
            continue

        tv_data = data.get("tv_data", {})

        label_title = data.get("title", "")

        if tv_data:
            season = tv_data.get("season")
            episode = tv_data.get("episode")
            show_name = tv_data.get("name", "")
            label = f"{show_name} S{season:02d}E{episode:02d}"
        else:
            label = label_title

        list_item = ListItem(label=label)

        # Set Art
        icon = os.path.join(ADDON_PATH, "resources", "img", "magnet.png")

        # Try to find art in data
        art = {}
        if data.get("poster"):
            art["poster"] = data.get("poster")
        if data.get("fanart"):
            art["fanart"] = data.get("fanart")
        if not art:
            art["icon"] = icon
        list_item.setArt(art)

        # Set Info
        info_tag = list_item.getVideoInfoTag()
        info_tag.setTitle(label)
        info_tag.setPlot(data.get("overview", ""))

        if "current_time" in data and "total_time" in data:
            try:
                current_time = float(data["current_time"])
                total_time = float(data["total_time"])
                info_tag.setResumePoint(current_time, total_time)
            except ValueError:
                pass

        list_item.setProperty("PercentPlayed", str(progress))

        list_item.setProperty("IsPlayable", "true")
        context_menu = add_last_files_context_menu(data)
        context_menu.append(
            (
                translation(90206),
                f"RunPlugin({build_url('remove_continue_watching', title=title)})",
            )
        )
        list_item.addContextMenuItems(context_menu)

        # url to play
        url = build_url("play_media", data=json.dumps(data))

        addDirectoryItem(ADDON_HANDLE, url, list_item, False)
        count += 1

    if count == 0:
        pass

    end_of_directory(cache=False)
