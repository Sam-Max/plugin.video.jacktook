import json
import os
import ssl
import threading
import re
import time
from urllib.request import Request, urlopen
from urllib.parse import parse_qsl, unquote, urlparse
from lib.utils.general.utils import set_pluging_category, supported_video_extensions
from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    apply_section_view,
    action_url_run,
    build_url,
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
from lib.download_manager import DownloadManager
from lib.gui.custom_progress import CustomProgressDialog
from lib.nav.debrid import resolve_cloud_download_url

from xbmcplugin import (
    addDirectoryItems,
    endOfDirectory,
    setContent,
)
import xbmcgui
import xbmcvfs
import xbmc

cancel_flag_cache = MemoryCache()


def handle_download_file(params):
    destination = params.get("destination")
    if not destination or not os.path.exists(destination):
        kodilog(f"[Downloader] Invalid download destination: {destination}")
        notification("Invalid download destination.")
        return

    url = params.get("url", "")
    file_name = normalize_file_name(params.get("file_name", ""), url)
    dest_path = os.path.join(destination, file_name)
    cancel_key = dest_path
    kodilog(f"[Downloader] handle_download_file: file_name={file_name}, dest_path={dest_path}, url_length={len(url)}")

    manager = DownloadManager()
    entry = manager.register(name=file_name, dest_path=dest_path, url=url)
    if entry is None:
        kodilog(f"[Downloader] Download already in progress: {dest_path}")
        notification("Download already in progress.")
        return

    downloader = Downloader(
        url=url,
        destination=destination,
        name=file_name,
        registry_id=dest_path,
    )
    cancel_flag_cache.set(cancel_key, downloader.is_cancelled)
    thread = downloader.run()
    if thread:
        manager.set_thread(dest_path, thread)
        kodilog(f"[Downloader] Download thread started for: {dest_path}")
    else:
        kodilog(f"[Downloader] Failed to start download thread for: {dest_path}")


def download_cloud_file(params):
    url = params.get("url", "")
    filename = params.get("filename", "")
    mode = params.get("mode", "movie")
    debrid_type = params.get("debrid_type", "")

    if not url and debrid_type == "TB":
        url = resolve_cloud_download_url({
            "debrid_type": debrid_type,
            "torrent_id": params.get("torrent_id", ""),
            "file_id": params.get("file_id", ""),
        })

    if not url:
        notification("Download link unavailable.")
        return

    dest_data = {"title": filename, "mode": "movies" if mode in ("movie", "movies") else mode}
    destination = get_destination_path(dest_data)
    if not destination or not os.path.exists(destination):
        notification("Invalid download destination.")
        return

    file_name = normalize_file_name(filename, url)
    dest_path = os.path.join(destination, file_name)

    manager = DownloadManager()
    entry = manager.register(name=file_name, dest_path=dest_path, url=url)
    if entry is None:
        notification("Download already in progress.")
        return

    downloader = Downloader(
        url=url,
        destination=destination,
        name=file_name,
        registry_id=dest_path,
    )
    thread = downloader.run()
    if thread:
        manager.set_thread(dest_path, thread)


def get_destination_path(data):
    download_dir = get_setting("download_dir")
    destination = translatePath(download_dir)

    if not get_setting("organize_downloads", False):
        return destination

    mode = data.get("mode", "")
    if mode == "movies":
        movies_folder = get_setting("download_folder_movies", "Movies")
        destination = os.path.join(destination, movies_folder)
    elif mode == "tv":
        tv_data = data.get("tv_data", {})
        show_name = tv_data.get("name") or data.get("title", "")
        season = tv_data.get("season", 1)
        tvshows_folder = get_setting("download_folder_tvshows", "TV Shows")
        destination = os.path.join(
            destination,
            tvshows_folder,
            show_name,
            f"Season {int(season):02d}",
        )

    xbmcvfs.mkdirs(destination)
    return destination


def download_video(params):
    data = json.loads(params["data"])
    destination = get_destination_path(data)
    handle_download_file(
        {"destination": destination, "file_name": data["title"], "url": data["url"]}
    )


class ProgressHandler:
    def update(self, percent: int, message: str, downloaded_str: str = "", size_str: str = "", speed_str: str = "", eta_str: str = ""):
        pass

    def cancelled(self) -> bool:
        return False

    def close(self):
        pass


class KodiProgressHandler(ProgressHandler):
    def __init__(self, title: str, addon_path: str):
        self.dialog = CustomProgressDialog("custom_progress_dialog.xml", addon_path)
        self.dialog.show_dialog()

    def update(self, percent: int, message: str, downloaded_str: str = "", size_str: str = "", speed_str: str = "", eta_str: str = ""):
        self.dialog.update_progress(percent, message, downloaded_str, size_str, speed_str, eta_str)

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
        registry_id: str = None,
        show_progress: bool = True,
    ):
        self.url = url
        self.destination = destination
        self.name = name
        self.registry_id = registry_id
        self.show_progress = show_progress
        self.headers = {}
        self.file_size = 0
        self.monitor = xbmc.Monitor()
        self.progress_handler = None
        self.is_cancelled = False
        self.dest_path = os.path.join(destination, name)
        self.temp_path = self.dest_path + ".part"
        self.meta_path = self.dest_path + ".jacktook.json"
        self._start_time = None

    def _write_metadata(self, status: str, progress: int = 0, size: int = 0, downloaded: int = 0, speed: int = 0, eta: int = 0):
        try:
            meta = {
                "title": self.name,
                "url": self.url,
                "status": status,
                "progress": progress,
                "size": size,
                "downloaded": downloaded,
                "speed": speed,
                "eta": eta,
            }
            with open(self.meta_path, "w") as f:
                json.dump(meta, f)
        except Exception as e:
            kodilog(f"[Downloader] Failed to write metadata: {str(e)}")

    def _update_registry(self, downloaded: int, percent: int):
        if not self.registry_id:
            return
        speed = 0
        eta = 0
        if self._start_time is not None:
            elapsed = time.time() - self._start_time
            if elapsed > 0:
                speed = int(downloaded / elapsed)
            remaining = self.file_size - downloaded
            if speed > 0 and remaining > 0:
                eta = int(remaining / speed)
            else:
                eta = 0
        DownloadManager().update_progress(
            self.registry_id,
            downloaded=downloaded,
            speed=speed,
            eta=eta,
            progress=percent,
            size=self.file_size,
        )

    def _set_registry_status(self, status: str):
        if not self.registry_id:
            return
        DownloadManager().set_status(self.registry_id, status)

    def _is_cancelled(self):
        if self.progress_handler and self.progress_handler.cancelled():
            return True
        if cancel_flag_cache.get(self.dest_path) is True:
            return True
        if self.registry_id:
            entry = DownloadManager().get_entry(self.registry_id)
            if entry and entry.cancel_flag:
                return True
        return False

    def run(self):
        if not self.url:
            notification("No URL provided for download.")
            return None
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()
        return thread

    def _run(self):
        # Show progress dialog immediately, before network calls
        if self.show_progress:
            self.progress_handler = KodiProgressHandler("Downloading", ADDON_PATH)
            self.progress_handler.update(0, translation(90807))
        else:
            self.progress_handler = ProgressHandler()

        self._prepare_url()
        if not self._validate_url():
            notification("Invalid URL for download.")
            self.progress_handler.close()
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
            if not self.headers.get("User-Agent"):
                from lib.utils.general.utils import USER_AGENT_STRING

                self.headers["User-Agent"] = USER_AGENT_STRING

            request = Request(self.url, headers=self.headers)
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            response = urlopen(request, context=context)
            self.file_size = int(response.headers.get("Content-Length", 0))
            return True
        except Exception as e:
            kodilog(f"[Downloader] Validation error: {str(e)}")
            return False

    def _start_download(self):
        downloaded = 0
        file_mode = "wb"

        # Ensure progress handler exists (may already be set by _run)
        if self.progress_handler is None:
            if self.show_progress:
                self.progress_handler = KodiProgressHandler("Downloading", ADDON_PATH)
            else:
                self.progress_handler = ProgressHandler()

        self._write_metadata("downloading", 0)
        self._set_registry_status("downloading")
        self._start_time = time.time()

        try:
            # Resume support — check temp file
            if os.path.exists(self.temp_path):
                downloaded = os.path.getsize(self.temp_path)
                if downloaded < self.file_size:
                    self.headers["Range"] = f"bytes={downloaded}-"
                    file_mode = "ab"
                elif downloaded >= self.file_size:
                    # Temp file is complete but not renamed yet
                    if xbmcvfs.exists(self.temp_path):
                        xbmcvfs.rename(self.temp_path, self.dest_path)
                    self._write_metadata("completed", 100)
                    self._set_registry_status("completed")
                    notification(f"File already downloaded: {self.name}")
                    return

            # Also check if final file already exists
            if os.path.exists(self.dest_path):
                downloaded = os.path.getsize(self.dest_path)
                if downloaded >= self.file_size:
                    self._write_metadata("completed", 100)
                    self._set_registry_status("completed")
                    notification(f"File already downloaded: {self.name}")
                    return

            request = Request(self.url, headers=self.headers)
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            response = urlopen(request, context=context)

            with open_file(self.temp_path, file_mode) as file:
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

                    # Calculate speed and ETA for progress display
                    speed_str = ""
                    eta_str = ""
                    if self._start_time is not None:
                        elapsed = time.time() - self._start_time
                        if elapsed > 0:
                            speed = int(downloaded / elapsed)
                            speed_str = f"{bytes_to_human_readable(speed)}/s"
                            remaining = self.file_size - downloaded
                            if speed > 0 and remaining > 0:
                                eta_secs = int(remaining / speed)
                                eta_mins, eta_secs = divmod(eta_secs, 60)
                                eta_hrs, eta_mins = divmod(eta_mins, 60)
                                if eta_hrs:
                                    eta_str = f"{eta_hrs}h {eta_mins}m"
                                elif eta_mins:
                                    eta_str = f"{eta_mins}m {eta_secs}s"
                                else:
                                    eta_str = f"{eta_secs}s"
                            else:
                                eta_str = ""

                    self.progress_handler.update(
                        percent,
                        self.name,
                        f"{bytes_to_human_readable(downloaded)} / {bytes_to_human_readable(self.file_size)}",
                        f"{percent}%",
                        speed_str,
                        eta_str,
                    )
                    self._write_metadata("downloading", percent)
                    self._update_registry(downloaded, percent)

                    # Handle cancellation
                    if self._is_cancelled():
                        cancel_flag_cache.set(self.dest_path, True)
                        self.is_cancelled = True
                        self._write_metadata("paused", percent)
                        self._set_registry_status("paused")
                        file.close()
                        break

                    self.monitor.waitForAbort(0.1)

                if self.is_cancelled:
                    meta = get_download_metadata(self.dest_path)
                    if meta.get("status") == "paused":
                        notification(f"Download paused: {self.name}")
                    else:
                        notification(f"Download cancelled: {self.name}")
                else:
                    # Rename temp to final on success
                    if xbmcvfs.exists(self.temp_path):
                        xbmcvfs.rename(self.temp_path, self.dest_path)
                    self._write_metadata("completed", 100)
                    self._set_registry_status("completed")
                    notification(f"Download completed: {self.name}")
        except Exception as e:
            self._set_registry_status("error")
            notification(f"Download error: {str(e)}")
        finally:
            if self.progress_handler:
                self.progress_handler.close()


def handle_cancel_download(params):
    file_path = json.loads(params.get("file_path"))
    if file_path:
        cancel_flag_cache.set(file_path, True)
        xbmc.executebuiltin("Container.Refresh")
    else:
        notification("No active download found.")


def handle_pause_download(params, refresh=True):
    file_path = json.loads(params.get("file_path"))
    if file_path:
        # Derive final path (strip .part if present)
        final_path = file_path[:-5] if file_path.endswith(".part") else file_path
        cancel_flag_cache.set(final_path, True)
        meta_path = final_path + ".jacktook.json"
        try:
            if os.path.exists(meta_path):
                with open(meta_path, "r") as f:
                    meta = json.load(f)
                meta["status"] = "paused"
                with open(meta_path, "w") as f:
                    json.dump(meta, f)
        except Exception as e:
            kodilog(f"[Downloader] Failed to update pause metadata: {str(e)}")
        if refresh:
            xbmc.executebuiltin("Container.Refresh")
    else:
        notification("No active download found.")


def resume_download(params):
    file_path = json.loads(params.get("file_path"))
    if not file_path:
        notification("File not found.")
        return

    # Derive final path (strip .part if present)
    final_path = file_path[:-5] if file_path.endswith(".part") else file_path
    temp_path = final_path + ".part"

    # Must have at least the temp file or the final file
    if not os.path.exists(temp_path) and not os.path.exists(final_path):
        notification("File not found.")
        return

    meta_path = final_path + ".jacktook.json"
    try:
        with open(meta_path, "r") as f:
            meta = json.load(f)
    except Exception as e:
        kodilog(f"[Downloader] Failed to read metadata for resume: {str(e)}")
        notification("No metadata found for resume.")
        return

    cancel_flag_cache.set(final_path, False)
    downloader = Downloader(
        url=meta.get("url", ""),
        destination=os.path.dirname(final_path),
        name=os.path.basename(final_path),
    )
    downloader.run()


def get_download_metadata(path):
    # Derive final path (strip .part if present)
    final_path = path[:-5] if path.endswith(".part") else path
    meta_path = final_path + ".jacktook.json"
    defaults = {"status": "unknown", "progress": 0, "title": ""}
    try:
        if os.path.exists(meta_path):
            with open(meta_path, "r") as f:
                meta = json.load(f)
            defaults.update(meta)
    except Exception:
        pass
    return defaults


def handle_delete_file(params):
    file_path = json.loads(params.get("file_path"))
    if not xbmcvfs.exists(file_path):
        notification("File not found.")
        return
    try:
        xbmcvfs.delete(file_path)
        # Also delete the temp .part file if it exists
        final_path = file_path[:-5] if file_path.endswith(".part") else file_path
        temp_path = final_path + ".part"
        if xbmcvfs.exists(temp_path):
            xbmcvfs.delete(temp_path)
        meta_path = final_path + ".jacktook.json"
        if xbmcvfs.exists(meta_path):
            xbmcvfs.delete(meta_path)
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
        setContent(ADDON_HANDLE, "files")
        directories, files = xbmcvfs.listdir(translated_path)
        active_downloads = [
            f for f in files if is_active_download(os.path.join(translated_path, f))
        ]

        active_label = (
            f"[COLOR red]{translation(90373)}: {len(active_downloads)}[/COLOR]"
        )
        active_item = xbmcgui.ListItem(label=active_label)
        active_item.setProperty("IsPlayable", "false")
        active_item.setArt(
            {"icon": os.path.join(ADDON_PATH, "resources", "img", "download.png")}
        )
        item_list.append(("", active_item, False))

        for item in directories + files:
            item_path = os.path.join(translated_path, item)

            # Skip metadata files
            if item.endswith(".jacktook.json"):
                continue

            if item in directories:
                list_item = xbmcgui.ListItem(label=item)
                info_tag = list_item.getVideoInfoTag()
                info_tag.setTitle(item)
                info_tag.setMediaType("folder")
                list_item.setProperty("IsPlayable", "false")
                is_folder = True
            else:
                # Strip .part for display but keep it for internal path
                display_name = item[:-5] if item.endswith(".part") else item
                meta = get_download_metadata(item_path)
                status = meta.get("status", "unknown")
                progress = meta.get("progress", 0)

                if status == "completed":
                    label = f"[COLOR green][OK][/COLOR] {display_name}"
                elif status == "paused":
                    label = f"[COLOR orange][PAUSED][/COLOR] {display_name} ({progress}%)"
                elif status == "downloading":
                    label = f"[COLOR red][DL][/COLOR] {display_name}"
                else:
                    label = display_name

                list_item = xbmcgui.ListItem(label=label)
                info_tag = list_item.getVideoInfoTag()
                info_tag.setTitle(display_name)
                info_tag.setMediaType("file")

                # Make completed files playable directly via plugin URL
                if status == "completed" and not item.endswith(".part"):
                    play_url = build_url("play_url", url=item_path, name=display_name)
                    list_item.setProperty("IsPlayable", "true")
                    list_item.setPath(play_url)
                else:
                    list_item.setProperty("IsPlayable", "false")

                context_menu = []

                if status == "downloading":
                    context_menu.append(
                        (
                            translation(90777),
                            action_url_run(
                                "handle_pause_download",
                                file_path=json.dumps(item_path),
                            ),
                        )
                    )
                elif status == "paused":
                    context_menu.append(
                        (
                            translation(90778),
                            action_url_run(
                                "resume_download",
                                file_path=json.dumps(item_path),
                            ),
                        )
                    )
                elif is_active_download(item_path):
                    context_menu.append(
                        (
                            translation(90374),
                            action_url_run(
                                "handle_cancel_download",
                                file_path=json.dumps(item_path),
                            ),
                        )
                    )

                if status in ("completed", "paused"):
                    context_menu.append(
                        (
                            translation(90782),
                            action_url_run(
                                "handle_delete_file", file_path=json.dumps(item_path)
                            ),
                        )
                    )

                list_item.addContextMenuItems(context_menu)
                is_folder = False

                # Use plugin URL for playable completed files so Kodi routes
                # them through play_url for proper resolution
                if status == "completed" and not item.endswith(".part"):
                    listing_url = build_url("play_url", url=item_path, name=display_name)
                else:
                    listing_url = item_path
            item_list.append((listing_url, list_item, is_folder))

        addDirectoryItems(ADDON_HANDLE, item_list)
        endOfDirectory(ADDON_HANDLE)
        apply_section_view("view.downloads", content_type="files")
    except Exception as e:
        notification(f"Error: {str(e)}", translation(90662))
        endOfDirectory(ADDON_HANDLE, succeeded=False)


def is_active_download(path):
    meta = get_download_metadata(path)
    if meta["status"] == "downloading":
        return True
    if meta["status"] in ("paused", "completed"):
        return False
    cancel_flag = cancel_flag_cache.get(path)
    return cancel_flag is not True


def normalize_file_name(file_name, url=""):
    file_name = (file_name or "").strip()
    valid_extensions = {ext.lower() for ext in supported_video_extensions()}

    base, ext = os.path.splitext(file_name)
    if ext.lower() not in valid_extensions:
        base = file_name
        ext = ""

    if not base and url:
        url_path = unquote(urlparse(url.split("|", 1)[0]).path)
        base = os.path.splitext(os.path.basename(url_path))[0]

    if not ext and url:
        url_path = unquote(urlparse(url.split("|", 1)[0]).path)
        _, url_ext = os.path.splitext(url_path)
        if url_ext.lower() in valid_extensions:
            ext = url_ext

    # Remove invalid characters and dots from base name
    base = re.sub(r'[\\/*?:"<>|.]', "_", base)
    base = re.sub(r"_+", "_", base)
    return f"{base}{ext}"
