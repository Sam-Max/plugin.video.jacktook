import json
import os
import ssl
import threading
import re
from urllib.request import Request, urlopen
from urllib.parse import parse_qsl
from lib.utils.general.utils import set_pluging_category
from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    action_url_run,
    bytes_to_human_readable,
    get_setting,
    kodilog,
    translatePath,
    ADDON_PATH,
    notification,
    open_file,
    translation,
)
from lib.db.cached import MemoryCache
from lib.gui.custom_progress import CustomProgressDialog

from xbmcplugin import (
    addDirectoryItems,
    endOfDirectory,
)
import xbmcgui
import xbmcvfs
import xbmc


cancel_flag_cache = MemoryCache()


def handle_download_file(params):
    destination = params.get("destination")
    if not destination or not os.path.exists(destination):
        notification("Invalid download destination.")
        return

    file_name = normalize_file_name(params.get("file_name", ""))
    cancel_key = os.path.join(destination, file_name)
    kodilog(f"Setting cancel event cache key: {cancel_key}")

    downloader = Downloader(
        url=params.get("url"),
        destination=destination,
        name=file_name,
    )
    cancel_flag_cache.set(cancel_key, downloader.is_cancelled)
    downloader.run()


def download_video(params):
    data = json.loads(params["data"])
    download_dir = get_setting("download_dir")
    destination = translatePath(download_dir)
    handle_download_file(
        {"destination": destination, "file_name": data["title"], "url": data["url"]}
    )


class ProgressHandler:
    def update(self, percent: int, message: str):
        pass

    def cancelled(self) -> bool:
        return False

    def close(self):
        pass


class KodiProgressHandler(ProgressHandler):
    def __init__(self, title: str, addon_path: str):
        self.dialog = CustomProgressDialog("custom_progress_dialog.xml", addon_path)
        self.dialog.show_dialog()

    def update(self, percent: int, message: str):
        self.dialog.update_progress(percent, message)

    def cancelled(self) -> bool:
        return self.dialog.cancelled

    def close(self):
        self.dialog.close()


class Downloader:
    def __init__(
        self,
        url: str,
        destination: str,
        name: str,
    ):
        self.url = url
        self.destination = destination
        self.name = name
        self.headers = {}
        self.file_size = 0
        self.monitor = xbmc.Monitor()
        self.progress_handler = None
        self.is_cancelled = False
        self.dest_path = os.path.join(destination, name)

    def run(self):
        if not self.url:
            notification("No URL provided for download.")
            return
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()

    def _run(self):
        self._prepare_url()
        if not self._validate_url():
            notification("Invalid URL for download.")
            return
        self._start_download()

    def _prepare_url(self):
        try:
            if "|" in self.url:
                self.headers = dict(parse_qsl(self.url.rsplit("|", 1)[1]))
                self.url = self.url.split("|")[0]
        except Exception as e:
            kodilog(f"[Downloader] Failed to parse headers: {str(e)}")

    def _validate_url(self):
        try:
            request = Request(self.url, headers=self.headers)
            response = urlopen(request, context=ssl.SSLContext(ssl.PROTOCOL_SSLv23))
            self.file_size = int(response.headers.get("Content-Length", 0))
            return self.file_size > 0
        except Exception as e:
            kodilog(f"[Downloader] Validation error: {str(e)}")
            return False

    def _start_download(self):
        downloaded = 0
        file_mode = "wb"

        self.progress_handler = KodiProgressHandler("Downloading", ADDON_PATH)

        try:
            # Resume support
            if os.path.exists(self.dest_path):
                downloaded = os.path.getsize(self.dest_path)
                if downloaded < self.file_size:
                    self.headers["Range"] = f"bytes={downloaded}-"
                    file_mode = "ab"
                elif downloaded >= self.file_size:
                    notification(f"File already downloaded: {self.name}")
                    return

            request = Request(self.url, headers=self.headers)
            response = urlopen(request, context=ssl.SSLContext(ssl.PROTOCOL_SSLv23))

            with open_file(self.dest_path, file_mode) as file:
                while not self.monitor.abortRequested():
                    chunk = response.read(1024 * 1024)  # 1MB chunks
                    if not chunk:
                        kodilog("No more data to read")
                        break

                    file.write(chunk)
                    downloaded += len(chunk)

                    if self.file_size:
                        percent = int((downloaded / self.file_size) * 100)
                    else:
                        percent = 0

                    self.progress_handler.update(
                        percent,
                        f"{self.name} - {percent}% - {bytes_to_human_readable(downloaded)} / {bytes_to_human_readable(self.file_size)}",
                    )

                    # Handle cancellation
                    if (
                        self.progress_handler.cancelled()
                        or cancel_flag_cache.get(self.dest_path) is True
                    ):
                        cancel_flag_cache.set(self.dest_path, True)
                        self.is_cancelled = True
                        file.close()
                        break

                    self.monitor.waitForAbort(0.1)

                if self.is_cancelled:
                    notification(f"Download cancelled: {self.name}")
                else:
                    notification(f"Download completed: {self.name}")
        except Exception as e:
            notification(f"Download error: {str(e)}")
        finally:
            self.progress_handler.close()


def handle_cancel_download(params):
    file_path = json.loads(params.get("file_path"))
    if file_path:
        cancel_flag_cache.set(file_path, True)
        xbmc.executebuiltin("Container.Refresh")
    else:
        notification("No active download found.")


def handle_delete_file(params):
    file_path = json.loads(params.get("file_path"))
    if not xbmcvfs.exists(file_path):
        notification("File not found.")
        return
    try:
        xbmcvfs.delete(file_path)
        notification(f"File Deleted")
        xbmc.executebuiltin("Container.Refresh")
    except Exception as e:
        kodilog(f"Error deleting file: {str(e)}")
        notification(f"Failed to delete file: {str(e)}")


def downloads_viewer(params):
    set_pluging_category(translation(90015))
    translated_path = translatePath(get_setting("download_dir"))
    item_list = []

    try:
        directories, files = xbmcvfs.listdir(translated_path)
        active_downloads = [
            f for f in files if is_active_download(os.path.join(translated_path, f))
        ]

        active_label = f"[COLOR red]Active Downloads: {len(active_downloads)}[/COLOR]"
        active_item = xbmcgui.ListItem(label=active_label)
        active_item.setProperty("IsPlayable", "false")
        active_item.setArt(
            {"icon": os.path.join(ADDON_PATH, "resources", "img", "download.png")}
        )
        item_list.append(("", active_item, False))

        for item in directories + files:
            item_path = os.path.join(translated_path, item)
            list_item = xbmcgui.ListItem(label=item)
            if item in directories:
                list_item.setInfo("video", {"title": item, "mediatype": "folder"})
                list_item.setProperty("IsPlayable", "false")
                is_folder = True
            else:
                list_item.setInfo("video", {"title": item, "mediatype": "file"})
                context_menu = []

                if is_active_download(item_path):
                    context_menu.append(
                        (
                            "Cancel Download",
                            action_url_run(
                                "handle_cancel_download",
                                file_path=json.dumps(item_path),
                            ),
                        )
                    )

                context_menu.append(
                    (
                        "Delete File",
                        action_url_run(
                            "handle_delete_file", file_path=json.dumps(item_path)
                        ),
                    )
                )

                list_item.addContextMenuItems(context_menu)
                is_folder = False
            item_list.append((item_path, list_item, is_folder))

        addDirectoryItems(ADDON_HANDLE, item_list)
        endOfDirectory(ADDON_HANDLE)
    except Exception as e:
        notification(f"Error: {str(e)}", "Downloads Viewer")
        endOfDirectory(ADDON_HANDLE, succeeded=False)


def is_active_download(path):
    cancel_flag = cancel_flag_cache.get(path)
    return cancel_flag is not True


def normalize_file_name(file_name):
    file_name = file_name.strip()
    base, _ = os.path.splitext(file_name)
    # Remove invalid characters and dots from base name
    base = re.sub(r'[\\/*?:"<>|.]', "_", base)
    base = re.sub(r"_+", "_", base)
    return base
