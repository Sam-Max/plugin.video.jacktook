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
TORREST_ADDON_ID = "plugin.video.torrest"
ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo("path")
ADDON_ICON = ADDON.getAddonInfo("icon")
ADDON_ID = ADDON.getAddonInfo("id")
ADDON_VERSION = ADDON.getAddonInfo("version")
ADDON_NAME = ADDON.getAddonInfo("name")

progressDialog = xbmcgui.DialogProgress()


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


def set_setting(id, value):
    ADDON.setSetting(id=id, value=value)


def get_property(prop):
    return Window(10000).getProperty(prop)


def set_property(prop, value):
    return Window(10000).setProperty(prop, value)


def addon_settings():
    return xbmc.executebuiltin("Addon.OpenSettings(%s)" % ADDON_ID)


def addon_status():
    msg = f"[B]Jacktook Version[/B]: {ADDON_VERSION}\n\n"
    try:
        TORREST_ADDON = xbmcaddon.Addon("plugin.video.torrest")
        msg += f"[B]Torrest Server IP/Address[/B]: {TORREST_ADDON.getSetting('service_address')}\n"
        msg += f"[B]Torrest Server Port[/B]: {TORREST_ADDON.getSetting('port')}"
    except:
        pass
    return xbmcgui.Dialog().textviewer("Status", msg, False)


def is_torrest_addon():
    return xbmc.getCondVisibility(f"System.HasAddon({TORREST_ADDON_ID})")


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


def dialogyesno(header, text):
    dialog = xbmcgui.Dialog()
    confirmed = dialog.yesno(
        header,
        text,
    )
    if confirmed:
        return True
    else:
        return False


def close_all_dialog():
    execute_builtin("Dialog.Close(all,true)")


def container_update(plugin, func, *args, **kwargs):
    """
    Update the container to the specified path.

    :param path: The path where to update.
    :type path: str
    """
    return "Container.Update({})".format(plugin.url_for(func, *args, **kwargs))


def container_refresh():
    execute_builtin("Container.Refresh")


def run_plugin(plugin, func, *args, **kwargs):
    return xbmc.executebuiltin(
        "RunPlugin({})".format(plugin.url_for(func, *args, **kwargs))
    )


def action(plugin, func, *args, **kwargs):
    return "RunPlugin({})".format(plugin.url_for(func, *args, **kwargs))


def show_busy_dialog():
    execute_builtin("ActivateWindow(busydialognocancel)")


def container_refresh():
    execute_builtin("Container.Refresh")


def hide_busy_dialog():
    execute_builtin("Dialog.Close(busydialognocancel)")
    execute_builtin("Dialog.Close(busydialog)")


def get_cache_expiration():
    return get_int_setting("cache_expiration")


def execute_builtin(command, block=False):
    return executebuiltin(command, block)


def bytes_to_human_readable(size, unit="B"):
    units = {"B": 0, "KB": 1, "MB": 2, "GB": 3, "TB": 4, "PB": 5}

    while size >= 1024 and unit != "PB":
        size /= 1024
        unit = list(units.keys())[list(units.values()).index(units[unit] + 1)]

    return f"{size:.2f} {unit}"


def convert_size_to_bytes(size_str: str) -> int:
    """Convert size string to bytes."""
    match = re.match(r"(\d+(?:\.\d+)?)\s*(GB|MB)", size_str, re.IGNORECASE)
    if match:
        size, unit = match.groups()
        size = float(size)
        return int(size * 1024**3) if "GB" in unit.upper() else int(size * 1024**2)
    return 0


def sleep(miliseconds):
    xbmc.sleep(miliseconds)


def Keyboard(id, default="", hidden=False):
    keyboard = xbmc.Keyboard(default, translation(id), hidden)
    keyboard.doModal()
    if keyboard.isConfirmed():
        return keyboard.getText()


def copy2clip(txt):
    import subprocess

    platform = sys.platform

    if platform == "win32":
        try:
            cmd = "echo %s|clip" % txt.strip()
            return subprocess.check_call(cmd, shell=True)
        except:
            pass
    elif platform == "linux2":
        try:
            from subprocess import PIPE, Popen

            p = Popen(["xsel", "-pi"], stdin=PIPE)
            p.communicate(input=txt)
        except:
            pass
