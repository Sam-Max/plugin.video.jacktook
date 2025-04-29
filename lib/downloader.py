# -*- coding: utf-8 -*-
import os
import ssl
import threading
from urllib.request import Request, urlopen
from urllib.parse import parse_qsl, urlparse
from datetime import timedelta

from lib.api.jacktook.kodi import kodilog
from lib.utils.kodi_utils import (
    ADDON_HANDLE,
    get_setting,
    notification,
    translatePath,
)
from lib.db.cached import cache, MemoryCache
import xbmcplugin
import xbmcgui
from xbmcvfs import listdir
import xbmcvfs
import xbmc

# Use MemoryCache for cancel flags
cancel_flag_cache = MemoryCache()


def handle_download_file(params):
    """
    Handles the download process for a file using the Downloader class.
    """
    destination = params.get("destination")
    if not destination or not os.path.exists(destination):
        notification("Invalid download destination.")
        return

    # setup cancel flag and register by full filepath
    url = params.get("url", "")
    file_name = os.path.basename(urlparse(url).path)
    key = os.path.join(destination, file_name)

    cancel_flag = threading.Event()
    kodilog(f"Cancel flag: {cancel_flag}")
    kodilog(f"Key: {key}")
    cancel_flag_cache.set(key, cancel_flag, timedelta(hours=1))
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
            notification("No URL provided for download.")
            return

        thread = threading.Thread(target=self._run_download_process)
        thread.start()

    def _run_download_process(self):
        self._prepare_download()

        if not self._validate_url():
            notification("Invalid URL for download.")
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

            # Initialize the progress dialog
            progress_dialog = xbmcgui.DialogProgress()
            progress_dialog.create("Downloading", f"Starting download: {self.name}")

            with open(destination_path, "wb") as file:
                downloaded = 0
                while chunk := response.read(1024 * 1024):  # 1MB chunks
                    if self.cancel_flag and self.cancel_flag.is_set():
                        progress_dialog.close()
                        notification(f"Cancelled: {self.name}")
                        file.close()
                        try:
                            xbmcvfs.delete(destination_path)
                        except:
                            pass
                        return

                    file.write(chunk)
                    downloaded += len(chunk)
                    progress = int((downloaded / self.file_size) * 100)
                    progress_dialog.update(
                        progress,
                        f"{self.name}: {progress}% completed",
                    )

                    if progress_dialog.iscanceled():
                        progress_dialog.close()

            progress_dialog.close()
            notification(f"Successfully downloaded {self.name}.")
        except Exception as e:
            kodilog(f"Download error: {str(e)}")
            notification(f"Failed to download {self.name}: {str(e)}")
        finally:
            # Clean up registry
            key = os.path.join(self.destination, file_name)
            cache.delete(key)


def handle_cancel_download(params):
    kodilog("Cancelling download")
    file_path = params.get("file")
    cancel_flag = cancel_flag_cache.get(file_path, default=None)
    kodilog(f"Cancel key: {file_path}")
    kodilog(f"Cancel flag: {cancel_flag}")
    if cancel_flag:
        cancel_flag.set()
        kodilog(f"Cancelled download for {file_path}")
    else:
        notification("No active download found.")


def handle_delete_file(params):
    file_path = params.get("file")
    kodilog(f"Deleting file: {file_path}")
    if not xbmcvfs.exists(file_path):
        notification("File not found.")
        return
    try:
        xbmcvfs.delete(file_path)
        cancel_flag_cache.delete(file_path)
        notification(f"Deleted file: {os.path.basename(file_path)}")
        xbmc.executebuiltin("Container.Refresh")
    except Exception as e:
        kodilog(f"Error deleting file {file_path}: {str(e)}")
        notification(f"Failed to delete file: {str(e)}")


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
                    ),
                    (
                        "Delete File",
                        f"RunPlugin(plugin://plugin.video.jacktook?action=delete_file&file={item_path})",
                    ),
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
