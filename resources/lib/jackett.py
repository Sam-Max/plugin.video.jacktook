
import re
import requests
from resources.lib.client import Jackett
from resources.lib.database import Database
from resources.lib.util import bytes_to_human_readable, get_setting, hide_busy_dialog, notify, sort_results
from resources.lib.util import HANDLE, get_url, hide_busy_dialog
from urllib3.exceptions import InsecureRequestWarning
import xbmc
import xbmcgui
import xbmcplugin
from urllib.parse import quote


db = Database()

def get_client():
    url = get_setting('jackett_url')
    api_key = get_setting('jackett_apikey')

    if not url or not api_key:
        notify("You need to configure Jackett first")
        return

    if len(api_key) != 32:
        notify("Jackett API key is invalid")
        return
    
    return Jackett(db, url, api_key)

def search_jackett(tracker='', method=''):
    insecure = get_setting('jackett_insecure')
    if not insecure:
        # Disable the InsecureRequestWarning
        requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

    jackett = get_client()

    keyboard = xbmc.Keyboard("", "Search for torrents:", False)
    keyboard.doModal()
    if keyboard.isConfirmed():
        text = keyboard.getText().strip()
    else:
        hide_busy_dialog()
        return
    query = quote(text)

    res = jackett.search(query, tracker, method, insecure)
    if res:
        sorted_res= sort_results(res)
        show_results(sorted_res, jackett)


def show_results(result, client):
    description_length = int(get_setting('jackett_desc_length'))

    for r in result:
        title = r['Title']
        if len(title) > description_length:
            title = title[0:description_length]

        date = r['PublishDate']
        match = re.search(r"\d{4}-\d{2}-\d{2}", date)
        if match:
            date = match.group()

        size = bytes_to_human_readable(r['Size'])
        seeders = r['Seeders']
        description = r['Description']

        magnet = r['MagnetUri']
        url = r['Link']
        tracker = r['Tracker']

        watched = client.is_torrent_watched(title)
        if watched:
            title = f"[COLOR palevioletred]{title}[/COLOR]"

        torrent_title = f"[{tracker}] {title}[CR][I][LIGHT][COLOR lightgray]{date}, {size}, {seeders} seeds[/COLOR][/LIGHT][/I]"

        list_item = xbmcgui.ListItem(label=torrent_title)
        list_item.setInfo(
            "video",
            {"title": title, "mediatype": "video", "plot": description},
        )
        list_item.setProperty("IsPlayable", "true")
        is_folder = False
        xbmcplugin.addDirectoryItem(
            HANDLE,
            get_url(action="play_jackett", title=title, magnet=magnet, url=url),
            list_item,
            is_folder,
        )

    xbmcplugin.endOfDirectory(HANDLE)

def clear():
    dialog = xbmcgui.Dialog()
    confirmed = dialog.yesno(
        "Clear History",
        "Do you want to clear this history list?\n\nWatched statuses will be preserved.",
    )
    if confirmed:
        db.database["jt:history"] = {}
        db.commit()
        xbmc.executebuiltin("Container.Refresh")

def history():
    xbmcplugin.setPluginCategory(HANDLE, f"Jackett Torrents - History")

    list_item = xbmcgui.ListItem(label="Clear History")
    xbmcplugin.addDirectoryItem(
        HANDLE, get_url(action="clear_history"), list_item
    )

    for title, data in reversed(db.database["jt:history"].items()):
        formatted_time = data["timestamp"].strftime("%a, %d %b %Y %I:%M %p")
        label = f"[COLOR palevioletred]{title} [I][LIGHT]— {formatted_time}[/LIGHT][/I][/COLOR]"
        list_item = xbmcgui.ListItem(label=label)
        list_item.setProperty("IsPlayable", "true")
        is_folder = False
        xbmcplugin.addDirectoryItem(
            HANDLE, 
            get_url(action= "play_jackett", title=title, magnet=data.get("magnet", None),
                url=data.get("url", None)),
            list_item, 
            is_folder)

    xbmcplugin.endOfDirectory(HANDLE)