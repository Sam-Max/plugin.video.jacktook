#!/usr/bin/env python3
import sys
from urllib.parse import urlencode
import xbmc
import xbmcgui
import xbmcaddon
from resolveurl.lib import kodi
from xbmc import executebuiltin


_URL = sys.argv[0]
HANDLE = int(sys.argv[1])
VIDEO_FORMATS = list(filter(None, kodi.supported_video_extensions()))

__addon_id = _URL.replace('plugin://','').replace('/','')
__settings__ = xbmcaddon.Addon(id=__addon_id)

def get_setting(name, default=None):
    value = __settings__.getSetting(name)
    if not value: return default

    if value == "true":
        return True
    elif value == "false":
        return False
    else:
        return value

def log(x):
    xbmc.log("[HARU] " + str(x), xbmc.LOGINFO)


def get_url(**kwargs):
    return "{}?{}".format(_URL, urlencode(kwargs))


def set_art(list_item, artwork_url):
    if artwork_url:
        list_item.setArt({"poster": artwork_url, "thumb": artwork_url})


def slugify(text):
    return (
        text.lower()
        .replace(" ", "-")
        .replace(",", "")
        .replace("!", "")
        .replace("+", "")
    )

def compat(line1, line2, line3):
    message = line1
    if line2:
        message += '\n' + line2
    if line3:
        message += '\n' + line3
    return message

def dialog_ok(heading, line1, line2="", line3=""):
    return xbmcgui.Dialog().ok(heading, compat(line1=line1, line2=line2, line3=line3))

def execute_builtin(command, block=False):
    return executebuiltin(command, block)

def hide_busy_dialog():
    execute_builtin('Dialog.Close(busydialognocancel)')
    execute_builtin('Dialog.Close(busydialog)')

def convert_bytes(size, unit="B"):
    # Define the units and their respective size
    units = {"B": 0, "KB": 1, "MB": 2, "GB": 3, "TB": 4, "PB": 5}

    # Convert the size to the largest possible unit
    while size >= 1024 and unit != "PB":
        size /= 1024
        unit = list(units.keys())[list(units.values()).index(units[unit] + 1)]

    return f"{size:.2f} {unit}"