# -*- coding: utf-8 -*-
import os
import ssl
import threading
from urllib.request import Request, urlopen
from urllib.parse import parse_qsl, urlparse

from lib.api.jacktook.kodi import kodilog
from lib.utils.kodi_utils import (
    ADDON_HANDLE,
    get_setting,
    notification,
    bytes_to_human_readable,
    translatePath,
)
import xbmcplugin
import xbmcgui
from xbmcvfs import listdir
import xbmcvfs

active_downloads = {}


def handle_download_file(params):
    """
    Handles the download process for a file using the Downloader class.
    """
    destination = params.get("destination")
    if not destination or not os.path.exists(destination):
        notification("Download", "Invalid download destination.")
        return

    # setup cancel flag and register by full filepath
    cancel_flag = threading.Event()
    url = params.get("url", "")
    kodilog(f"Download URL: {url}")
    file_name = os.path.basename(urlparse(url).path)
    key = os.path.join(destination, file_name)
    active_downloads[key] = cancel_flag

    downloader = Downloader(params, cancel_flag)
    downloader.run()


class Downloader:
    def __init__(self, params, cancel_flag=None):
        self.url = params.get("url")
        self.name = params.get("title", "unknown")
        self.destination = params.get("destination", "")
        self.headers = {}
        self.file_size = 0
        self.cancel_flag = cancel_flag

    def run(self):
        if not self.url:
            notification("Download", "No URL provided for download.")
            return

        thread = threading.Thread(target=self._run_download_process)
        thread.start()

    def _run_download_process(self):
        self._prepare_download()

        if not self._validate_url():
            notification("Download", "Invalid URL for download.")
            return

        self._start_download()

    def _prepare_download(self):
        try:
            self.headers = dict(parse_qsl(self.url.rsplit("|", 1)[1]))
        except:
            self.headers = dict("")
        try:
            self.url = self.url.split("|")[0]
        except:
            pass

    def _validate_url(self):
        try:
            kodilog(f"Validating URL: {self.url}")
            request = Request(self.url, headers=self.headers)
            response = urlopen(request, context=ssl.SSLContext(ssl.PROTOCOL_SSLv23))
            kodilog(f"Response: {response.status} {response.reason}")
            self.file_size = int(response.headers.get("Content-Length", 0))
            return self.file_size > 0
        except Exception as e:
            kodilog(f"Error validating URL: {str(e)}")
            return False

    def _start_download(self):
        try:
            file_name = os.path.basename(urlparse(self.url).path)
            destination_path = os.path.join(self.destination, file_name)

            request = Request(self.url, headers=self.headers)
            response = urlopen(request, context=ssl.SSLContext(ssl.PROTOCOL_SSLv23))

            with open(destination_path, "wb") as file:
                downloaded = 0
                while chunk := response.read(1024 * 1024):  # 1MB chunks
                    # check for cancellation
                    if self.cancel_flag and self.cancel_flag.is_set():
                        notification(f"Cancelled: {self.name}", "Download")
                        file.close()
                        try:
                            os.remove(destination_path)
                        except:
                            pass
                        return

                    file.write(chunk)
                    downloaded += len(chunk)
                    progress = (downloaded / self.file_size) * 100
                    notification(
                        f"{self.name}: {progress:.2f}% ({bytes_to_human_readable(downloaded)} of {bytes_to_human_readable(self.file_size)})",
                        "Download Progress",
                        time=1000,
                        sound=False,
                    )

            notification(f"Successfully downloaded {self.name}.", "Download")
        except Exception as e:
            kodilog(f"Download error: {str(e)}")
            notification(f"Failed to download {self.name}: {str(e)}", "Download")
        finally:
            # clean up registry
            key = os.path.join(self.destination, file_name)
            active_downloads.pop(key, None)


def handle_cancel_download(params):
    file_path = params.get("file")
    flag = active_downloads.pop(file_path, None)
    if flag:
        flag.set()
    else:
        notification("No active download found.", "Download")


def downloads_viewer(params):
    download_dir = get_setting("download_dir")
    translated_path = translatePath(download_dir)

    item_list = []
    try:
        directories, files = listdir(translated_path)
        for item in directories + files:
            item_path = os.path.join(translated_path, item)
            list_item = xbmcgui.ListItem(label=item)
            if item in directories:
                list_item.setInfo("video", {"title": item, "mediatype": "folder"})
                list_item.setProperty("IsPlayable", "false")
                is_folder = True
            else:
                list_item.setInfo("video", {"title": item, "mediatype": "file"})
                context_menu = [
                    (
                        "Cancel Download",
                        f"RunPlugin(plugin://plugin.video.jacktook?action=cancel_download&file={item_path})",
                    )
                ]
                list_item.addContextMenuItems(context_menu)
                is_folder = False
            item_list.append((item_path, list_item, is_folder))

        xbmcplugin.addDirectoryItems(ADDON_HANDLE, item_list)
        xbmcplugin.addSortMethod(ADDON_HANDLE, xbmcplugin.SORT_METHOD_FILE)
        xbmcplugin.setContent(ADDON_HANDLE, "")
        xbmcplugin.setPluginCategory(ADDON_HANDLE, params.get("name", "Downloads"))
        xbmcplugin.endOfDirectory(ADDON_HANDLE)
    except Exception as e:
        notification(f"Error: {str(e)}", "Downloads Viewer")
        xbmcplugin.endOfDirectory(ADDON_HANDLE, succeeded=False)
