#!/usr/bin/env python3
from datetime import date, datetime, timedelta
import json
import re
import sys
import time
from typing import Any, Union

from urllib.parse import quote, urlencode
from lib.db.cached import cache
from lib.utils.kodi.logging import kodilog

import xbmc
import xbmcaddon
import xbmcgui

from xbmcgui import Window, ListItem
from xbmcplugin import addDirectoryItems, setResolvedUrl, endOfDirectory
from xbmcvfs import (
    translatePath as translate_path,
    delete as xbmc_delete,
    listdir,
    File as xbmcvfs_File,
)


_URL = sys.argv[0]

MOVIES_TYPE = "movies"
SHOWS_TYPE = "tvshows"
SEASONS_TYPE = "seasons"
EPISODES_TYPE = "episodes"
TITLES_TYPE = "titles"

TORREST_ADDON_ID = "plugin.video.torrest"
JACKTORR_ADDON_ID = "plugin.video.jacktorr"
ELEMENTUM_ADDON_ID = "plugin.video.elementum"
YOUTUBE_ADDON_ID = "plugin.video.youtube"
JACKTOOK_BURST_ADOON_ID = "script.jacktook.burst"


def _get_jacktorr_addon():
    try:
        if xbmc.getCondVisibility(f"System.HasAddon({JACKTORR_ADDON_ID})"):
            return xbmcaddon.Addon(JACKTORR_ADDON_ID)
    except Exception:
        pass
    return None


JACKTORR_ADDON = _get_jacktorr_addon()


ADDON = xbmcaddon.Addon()
try:
    ADDON_HANDLE = int(sys.argv[1])
except IndexError:
    ADDON_HANDLE = 0

ADDON_PATH = ADDON.getAddonInfo("path")
ADDON_PROFILE_PATH = translate_path(ADDON.getAddonInfo("profile"))
IMAGES_PATH = f"{ADDON_PATH}/resources/images/"
DEFAULT_LOGO = f"{IMAGES_PATH}tv.png"
ADDON_ICON = ADDON.getAddonInfo("icon")
ADDON_ID = ADDON.getAddonInfo("id")
ADDON_VERSION = ADDON.getAddonInfo("version")
ADDON_NAME = ADDON.getAddonInfo("name")
PLAYLIST = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)

CHANGELOG_PATH = translate_path(
    "special://home/addons/plugin.video.jacktook/CHANGELOG.md"
)

progressDialog = xbmcgui.DialogProgress()


def get_jacktorr_setting(value, default=None):
    if not JACKTORR_ADDON:
        notification(translation(30253))
        return
    value = JACKTORR_ADDON.getSetting(value)
    if not value:
        return default
    if isinstance(value, str):
        if value.lower() == "true":
            return True
        elif value.lower() == "false":
            return False
    return value


def _setting_cache_prop(setting_id: str) -> str:
    return f"jacktook.setting.{setting_id}"


def get_cached_setting_property(setting_id: str):
    return Window(10000).getProperty(_setting_cache_prop(setting_id))


def set_cached_setting_property(setting_id: str, value: Any):
    Window(10000).setProperty(_setting_cache_prop(setting_id), str(value))


def _normalize_setting_value(val, default=None):
    if not val:
        return default
    if isinstance(val, str):
        if val.lower() == "true":
            return True
        if val.lower() == "false":
            return False
    return val


def get_setting(id, default=None):
    val = get_cached_setting_property(id)
    if val:
        return _normalize_setting_value(val, default)

    val = ADDON.getSetting(id)
    if val:
        set_cached_setting_property(id, val)
        return _normalize_setting_value(val, default)

    return default


def set_setting(id, value):
    ADDON.setSetting(id, value)
    set_cached_setting_property(id, value)


def get_property_no_fallback(prop: str):
    return Window(10000).getProperty(prop)


def get_property(prop: str):
    value = Window(10000).getProperty(prop)
    kodilog(f"Get property: {prop} = {value}", xbmc.LOGDEBUG)
    if not value:
        value = cache.get(prop)
        kodilog(f"Get property from cache: {prop} = {value}", xbmc.LOGDEBUG)
        if not value:
            return None
    return value


def set_property_no_fallback(prop: str, value: Any):
    Window(10000).setProperty(prop, value)


def set_property(prop: str, value: Any):
    Window(10000).setProperty(prop, value)
    cache.set(prop, value, timedelta(days=30))


def clear_property(prop):
    return Window(10000).clearProperty(prop)


def burst_addon_settings():
    close_all_dialog()
    xbmc.executebuiltin("Addon.OpenSettings(%s)" % JACKTOOK_BURST_ADOON_ID)


def get_kodi_version():
    build = xbmc.getInfoLabel("System.BuildVersion")
    kodi_version = int(build.split()[0][:2])
    return kodi_version


def is_torrest_addon():
    return xbmc.getCondVisibility(f"System.HasAddon({TORREST_ADDON_ID})")


def is_jacktorr_addon():
    return xbmc.getCondVisibility(f"System.HasAddon({JACKTORR_ADDON_ID})")


def is_jacktorr_addon_enabled():
    try:
        if not xbmc.getCondVisibility(f"System.HasAddon({JACKTORR_ADDON_ID})"):
            return False
        addon = xbmcaddon.Addon(JACKTORR_ADDON_ID)
        # If the addon is disabled, this will raise RuntimeError
        return True
    except RuntimeError:
        # Addon exists but is disabled
        return False


def is_youtube_addon_enabled():
    try:
        if not xbmc.getCondVisibility(f"System.HasAddon({YOUTUBE_ADDON_ID})"):
            return False
        addon = xbmcaddon.Addon(YOUTUBE_ADDON_ID)
        # If the addon is disabled, this will raise RuntimeError
        return True
    except RuntimeError:
        # Addon exists but is disabled
        return False


def is_elementum_addon():
    return xbmc.getCondVisibility(f"System.HasAddon({ELEMENTUM_ADDON_ID})")


def is_burst_addon():
    return xbmc.getCondVisibility(f"System.HasAddon({JACKTOOK_BURST_ADOON_ID})")


def enable_addon(addon_id: str):
    """
    Enable a Kodi addon using JSON-RPC.
    Returns True if successful, False otherwise.
    """
    request = {
        "jsonrpc": "2.0",
        "method": "Addons.SetAddonEnabled",
        "params": {"addonid": addon_id, "enabled": True},
        "id": 1,
    }

    try:
        result = xbmc.executeJSONRPC(json.dumps(request))
        response = json.loads(result)
        return "error" not in response
    except Exception as e:
        xbmc.log(f"Failed to enable addon {addon_id}: {e}", level=xbmc.LOGERROR)
        return False


def translation(id_value):
    return ADDON.getLocalizedString(id_value)


def logger(message, level=xbmc.LOGINFO):
    xbmc.log("[JACKTOOK] " + str(message), level)


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


def kodi_refresh():
	execute_builtin('UpdateLibrary(video,special://skin/foo)')


def refresh():
    xbmc.executebuiltin("Container.Refresh")


def notification(message, heading=ADDON_NAME, icon=ADDON_ICON, time=2000, sound=True):
    xbmcgui.Dialog().notification(heading, message, icon, time, sound)


def dialog_ok(heading, line1, line2="", line3=""):
    return xbmcgui.Dialog().ok(heading, compat(line1=line1, line2=line2, line3=line3))


def dialog_text(heading: str, content: str = "", file=None):
    dialog = xbmcgui.Dialog()
    if file:
        try:
            with open(file, encoding="utf-8") as r:
                content = r.read()
        except Exception as e:
            logger(f"Error reading file {file}: {e}", xbmc.LOGERROR)
            notification("Error reading file.")
            return
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


def dialog_select(heading, _list):
    dialog = xbmcgui.Dialog()
    return dialog.select(heading, _list)


def close_all_dialog():
    execute_builtin("Dialog.Close(all,true)")


def container_update(name, **kwargs):
    """
    Update the container to the specified path.

    :param path: The path where to update.
    :type path: str
    """
    return "Container.Update({})".format(build_url(name, **kwargs))


def container_refresh():
    execute_builtin("Container.Refresh")


def action_url_run(name, **kwargs):
    return "RunPlugin({})".format(build_url(name, **kwargs))


def build_url(action, **params):
    for key, value in params.items():
        if isinstance(value, (dict, list)):
            params[key] = json.dumps(value)
    query = urlencode(params)
    return f"plugin://{ADDON_ID}/?action={action}&{query}"


def url_for(action, **kwargs):
    qs_kwargs = dict(((k, v) for k, v in list(kwargs.items())))
    query = "?" + urlencode(qs_kwargs) if qs_kwargs else ""
    return f"plugin://{ADDON_ID}/?action={action}&{query}"


def play_info_hash(info_hash):
    url = f"plugin://{JACKTORR_ADDON_ID}/play_info_hash?info_hash={quote(info_hash)}"
    return f"PlayMedia({url})"


def buffer_and_play(info_hash, file_id, path):
    url = f"plugin://{JACKTORR_ADDON_ID}/buffer_and_play?info_hash={info_hash}&file_id={file_id}&path={quote(path)}"
    return f"PlayMedia({url})"


def kodi_play_media(name, *args, **kwargs):
    return "PlayMedia({})".format(build_url(name, *args, **kwargs))


def show_busy_dialog():
    execute_builtin("ActivateWindow(busydialognocancel)")


def show_picture(url):
    xbmc.executebuiltin('ShowPicture("{}")'.format(url))


def close_busy_dialog():
    execute_builtin("Dialog.Close(busydialognocancel)")
    execute_builtin("Dialog.Close(busydialog)")


def execute_builtin(command, block=False):
    return xbmc.executebuiltin(command, block)


def get_visibility():
    return xbmc.getCondVisibility


def delete_file(file):
    xbmc_delete(file)


def update_local_addons():
    execute_builtin("UpdateLocalAddons", True)
    sleep(2500)


def disable_enable_addon(addon_id=ADDON_ID):
    try:
        xbmc.executeJSONRPC(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "Addons.SetAddonEnabled",
                    "params": {"addonid": addon_id, "enabled": False},
                }
            )
        )
        xbmc.executeJSONRPC(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "Addons.SetAddonEnabled",
                    "params": {"addonid": addon_id, "enabled": True},
                }
            )
        )
    except:
        pass


def update_kodi_addons_db(addon_id=ADDON_ID):
    try:
        import sqlite3 as database
        
        date = time.strftime("%Y-%m-%d %H:%M:%S")
        dbcon = database.connect(
            translate_path("special://database/Addons33.db"), timeout=40.0
        )
        dbcon.execute(
            "INSERT OR REPLACE INTO installed (addonID, enabled, lastUpdated) VALUES (?, ?, ?)",
            (addon_id, 1, date),
        )
        dbcon.close()
    except:
        pass


def bytes_to_human_readable(size: int, unit: str = "B") -> str:
    units = {"B": 0, "KB": 1, "MB": 2, "GB": 3, "TB": 4, "PB": 5}

    while size >= 1024 and unit != "PB":
        size /= 1024
        unit = list(units.keys())[list(units.values()).index(units[unit] + 1)]

    return f"{size:.3g} {unit}"


def convert_size_to_bytes(size_str: str) -> int:
    """Convert size string to bytes."""
    match = re.match(r"(\d+(?:\.\d+)?)\s*(GB|MB|KB|B)", size_str, re.IGNORECASE)
    if match:
        size, unit = match.groups()
        size = float(size)
        unit = unit.upper()
        if unit == "GB":
            return int(size * 1024**3)
        if unit == "MB":
            return int(size * 1024**2)
        if unit == "KB":
            return int(size * 1024)
        return int(size)
    return 0


def sleep(miliseconds):
    xbmc.sleep(miliseconds)


def show_keyboard(id, default="", hidden=False):
    keyboard = xbmc.Keyboard(default, translation(id), hidden)
    keyboard.doModal()
    if keyboard.isConfirmed():
        return keyboard.getText()


def get_current_view_id():
    return xbmcgui.Window(xbmcgui.getCurrentWindowId()).getFocusId()


SECTION_VIEW_KEYS = (
    "view.main",
    "view.movies",
    "view.tvshows",
    "view.seasons",
    "view.episodes",
    "view.library",
    "view.history",
    "view.downloads",
)


def get_view_setting_key(view_key):
    return "saved_%s" % view_key.replace(".", "_")


def get_view_property_key(view_key):
    return "jacktook.%s" % view_key


def _get_named_view_id(name, default="current"):
    views_dict = {
        "list": 50,
        "poster": 51,
        "iconwall": 52,
        "shift": 53,
        "infowall": 54,
        "widelist": 55,
        "wall": 500,
        "banner": 501,
        "fanart": 502,
        "current": get_current_view_id(),
    }
    return views_dict.get(name, views_dict.get(default))


def _normalize_container_content(content_type):
    content_map = {
        "": "",
        "files": "files",
        "tv": SHOWS_TYPE,
        "tvshow": SHOWS_TYPE,
        "shows": SHOWS_TYPE,
        "movie": MOVIES_TYPE,
        "season": SEASONS_TYPE,
        "episode": EPISODES_TYPE,
        "title": TITLES_TYPE,
        "video": "videos",
    }
    return content_map.get(content_type, content_type)


def _resolve_view_name(name, content_type=""):
    normalized_content = _normalize_container_content(content_type or container_content())
    if name in {"banner", "fanart"} and normalized_content in {
        MOVIES_TYPE,
        SHOWS_TYPE,
        SEASONS_TYPE,
        EPISODES_TYPE,
        TITLES_TYPE,
        "videos",
    }:
        return "poster"
    return name


def set_saved_view_property(view_key, view_id):
    set_property_no_fallback(get_view_property_key(view_key), str(view_id))


def save_view_id(view_key, view_id):
    if view_id in (None, "", 0, "0"):
        return False
    value = str(view_id)
    set_setting(get_view_setting_key(view_key), value)
    set_saved_view_property(view_key, value)
    return True


def get_saved_view_id(view_key):
    view_id = get_property_no_fallback(get_view_property_key(view_key))
    if not view_id:
        view_id = ADDON.getSetting(get_view_setting_key(view_key))
    return str(view_id) if view_id else None


def load_saved_view_properties():
    for view_key in SECTION_VIEW_KEYS:
        view_id = ADDON.getSetting(get_view_setting_key(view_key))
        if view_id:
            set_saved_view_property(view_key, view_id)


def capture_current_view_id():
    view_id = get_current_view_id()
    if view_id in (None, 0):
        return None
    return str(view_id)


def _wait_for_container_content(content_type, timeout_ms=2000):
    expected = _normalize_container_content(content_type)
    if not expected:
        return True
    elapsed = 0
    while elapsed <= timeout_ms:
        if _normalize_container_content(container_content()) == expected:
            return True
        sleep(50)
        elapsed += 50
    return False


def apply_section_view(view_key, content_type="", fallback=None, default="current"):
    _wait_for_container_content(content_type)
    saved_view_id = get_saved_view_id(view_key)
    if saved_view_id:
        execute_builtin(f"Container.SetViewMode({saved_view_id})")
        return saved_view_id
    fallback_name = _resolve_view_name(fallback or default, content_type=content_type)
    view_id = _get_named_view_id(fallback_name, default)
    if view_id:
        execute_builtin(f"Container.SetViewMode({view_id})")
    return view_id


def reset_saved_views():
    for view_key in SECTION_VIEW_KEYS:
        setting_key = get_view_setting_key(view_key)
        property_key = get_view_property_key(view_key)
        ADDON.setSetting(setting_key, "")
        clear_property(property_key)


def set_view(name, default="current"):
    view_id = _get_named_view_id(_resolve_view_name(name), default)
    execute_builtin(f"Container.SetViewMode({view_id})")


def container_content():
    return xbmc.getInfoLabel("Container.Content")


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


def get_datetime(string: bool = False, dt: bool = False) -> Union[date, datetime]:
    """
    Returns the current date/time in various formats.

    :param dt: If True, returns the full datetime object.
    :return: By default, returns a date object.
    """
    now = datetime.now()
    if dt:
        return now
    else:
        return now.date()


def list_dirs(location):
    return listdir(location)


def translatePath(_path):
    return translate_path(_path)


def open_file(_file, mode="r"):
    return xbmcvfs_File(_file, mode)


def cancel_playback():
    PLAYLIST.clear()
    close_busy_dialog()
    close_all_dialog()
    try:
        xbmc.Player().stop()
    except Exception:
        pass
    setResolvedUrl(ADDON_HANDLE, False, ListItem(offscreen=True))


def finish_action():
    setResolvedUrl(ADDON_HANDLE, False, ListItem(offscreen=True))


def make_list_item(label="", path="", offscreen=True):
    kwargs = {"offscreen": offscreen}
    if label:
        kwargs["label"] = label
    if path:
        kwargs["path"] = path
    return ListItem(**kwargs)


def add_directory_items_batch(items):
    if items:
        addDirectoryItems(ADDON_HANDLE, items)


def is_widget():
    return "jacktook" not in xbmc.getInfoLabel("Container.PluginName")


def end_of_directory(cache=True):
    endOfDirectory(
        ADDON_HANDLE, cacheToDisc=False if is_widget() or not cache else True
    )
