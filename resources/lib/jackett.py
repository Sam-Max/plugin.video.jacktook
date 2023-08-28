
import json
import logging
import requests
import re
import xbmc
import xbmcgui
import xbmcplugin
from urllib.parse import quote
from urllib3.exceptions import InsecureRequestWarning
from resources.lib.util import HANDLE, convert_bytes, dialog_ok, get_setting, get_url, hide_busy_dialog


class Jackett():
    def __init__(self, db) -> None:
        self.db = db
        self.load_settings()

    def load_settings(self):
        self.jackett_apikey = get_setting('jackett_apikey')
        self.jackett_url = get_setting('jackett_url')
        self.jackett_indexer = get_setting('jackett_indexer')
        self.description_length = int(get_setting('jackett_desc_length'))
        self.insecure = get_setting('jackett_insecure')
        if not self.insecure:
            # Disable the InsecureRequestWarning
            requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
        self.results_limit = get_setting('results_limit')

    def search(self):
        keyboard = xbmc.Keyboard("", "Search for torrents:", False)
        keyboard.doModal()
        if keyboard.isConfirmed():
            text = keyboard.getText().strip()
        else:
            hide_busy_dialog()
            return
        escaped = quote(text)
        try:
            url = f"{self.jackett_url}/api/v2.0/indexers/{self.jackett_indexer}/results?apikey={self.jackett_apikey}&Query={escaped}"
            r = requests.get(url, verify=self.insecure)
            if r.status_code != 200:
                dialog_ok("Haru", f"The request to Jackett failed. ({r.status_code})")
                return
            res = json.loads(r.content)
            res_count = len(res['Results'])
            logging.debug(f"Search yielded {str(res_count)} results.")
        except Exception as e:
            dialog_ok("Haru", f"The request to Jackett failed. {str(e)}")
            return

        for r in res['Results']:
            title = r['Title']
            if len(title) > self.description_length:
                title = title[0:self.description_length]

            date = r['PublishDate']
            match = re.search(r"\d{4}-\d{2}-\d{2}", date)
            if match:
                date = match.group()

            size = convert_bytes(r['Size'])
            seeders = r['Seeders']
            description = r['Description']

            magnet = r['MagnetUri']
            url = r['Link']
            tracker = r['Tracker']

            title = f"[{tracker}]{title}[CR][I][LIGHT][COLOR lightgray]{date}, {size}, {seeders} seeds[/COLOR][/LIGHT][/I]"

            list_item = xbmcgui.ListItem(label=title)
            list_item.setInfo(
                "video",
                {"title": title, "mediatype": "video", "plot": description},
            )
            list_item.setProperty("IsPlayable", "true")
            is_folder = False
            xbmcplugin.addDirectoryItem(
                HANDLE,
                get_url(action="play_jackett", magnet=magnet, url=url),
                list_item,
                is_folder,
            )

        xbmcplugin.endOfDirectory(HANDLE)
