#!/usr/bin/env python3
import re
import sys
from urllib.parse import urlencode
import xbmc
import xbmcgui
from xbmcgui import Window
import xbmcaddon
from xbmc import executebuiltin

_URL = sys.argv[0]
ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo("path")
ADDON_ICON = ADDON.getAddonInfo("icon")
ADDON_ID = ADDON.getAddonInfo("id")
ADDON_VERSION = ADDON.getAddonInfo("version")
ADDON_NAME = ADDON.getAddonInfo("name")


def get_setting(value, default=None):
    value = ADDON.getSetting(value)
    if not value:
        return default

    if value == "true":
        return True
    elif value == "false":
        return False
    else:
        return value


def get_property(prop):
    return Window(10000).getProperty(prop)


def set_setting(id, value):
    ADDON.setSetting(id, value)


def set_property(prop, value):
    return Window(10000).setProperty(prop, value)


def addon_settings():
    return xbmc.executebuiltin("Addon.OpenSettings(%s)" % ADDON_ID)


def addon_status():
    message = f"Version: {ADDON_VERSION}"
    return xbmcgui.Dialog().textviewer("Status", message, False)


def is_torrest_addon():
    return xbmc.getCondVisibility(f"System.HasAddon({ADDON_ID})")


def get_int_setting(setting):
    return int(get_setting(setting))


def translation(id_value):
    return ADDON.getLocalizedString(id_value)


def log(x):
    xbmc.log("[JACKTOOK] " + str(x), xbmc.LOGINFO)


def get_url(**kwargs):
    return "{}?{}".format(_URL, urlencode(kwargs))


def set_art(list_item, artwork_url):
    if artwork_url:
        list_item.setArt({"poster": artwork_url, "thumb": artwork_url})


def slugify(text):
    text = text.lower()
    text = re.sub(r"\[.*?\]", "", text)
    text = text.replace("(", "").replace(")", "")
    text = text.replace("'", "").replace("’", "")
    text = text.replace("+", "").replace("@", "")
    text = re.sub(r"[^a-zA-Z0-9_]+", "-", text)
    text = text.strip("-")
    return text


def compat(line1, line2, line3):
    message = line1
    if line2:
        message += "\n" + line2
    if line3:
        message += "\n" + line3
    return message


def notify(message, image=ADDON_ICON):
    xbmcgui.Dialog().notification(ADDON_NAME, message, icon=image, sound=False)


def dialog_ok(heading, line1, line2="", line3=""):
    return xbmcgui.Dialog().ok(heading, compat(line1=line1, line2=line2, line3=line3))


def dialog_text(heading, content):
    dialog = xbmcgui.Dialog()
    dialog.textviewer(heading, content, False)
    return dialog


def close_all_dialog():
    execute_builtin("Dialog.Close(all,true)")


def execute_builtin(command, block=False):
    return executebuiltin(command, block)


def run_plugin(plugin):
    xbmc.executebuiltin("RunPlugin({})".format(plugin))


def container_refresh():
    execute_builtin("Container.Refresh")


def hide_busy_dialog():
    execute_builtin("Dialog.Close(busydialog)")


def get_cache_expiration():
    return get_int_setting("cache_expiration")


def bytes_to_human_readable(size, unit="B"):
    units = {"B": 0, "KB": 1, "MB": 2, "GB": 3, "TB": 4, "PB": 5}

    while size >= 1024 and unit != "PB":
        size /= 1024
        unit = list(units.keys())[list(units.values()).index(units[unit] + 1)]

    return f"{size:.2f} {unit}"


def Keyboard(id, default="", hidden=False):
    keyboard = xbmc.Keyboard(default, translation(id), hidden)
    keyboard.doModal()
    if keyboard.isConfirmed():
        return keyboard.getText()
