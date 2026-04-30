import json
import os
import threading
import time

import xbmc
import xbmcgui
import xbmcvfs

from lib.download_manager import DownloadManager
from lib.downloader import Downloader, cancel_flag_cache, get_download_metadata, handle_pause_download, resume_download
from lib.gui.base_window import BaseWindow
from lib.utils.kodi.settings import get_setting as _get_setting
from lib.utils.kodi.utils import ADDON_PATH, bytes_to_human_readable, execute_builtin, kodilog, translatePath as _translatePath, translation


class DownloadManagerWindow(BaseWindow):
    def __init__(self, xml_file, location, item_information=None, previous_window=None):
        super().__init__(xml_file, location, item_information, previous_window)
        self._monitor = xbmc.Monitor()
        self._closed = False
        self._poll_thread = None
        self._focused_item_id = None
        self._last_registry_checksum = ""

    def onInit(self):
        self.setProperty("instant_close", "false")
        self._sync_from_disk()
        self._rebuild_list()
        self._poll_thread = threading.Thread(target=self._poll_loop)
        self._poll_thread.daemon = True
        self._poll_thread.start()

    def _sync_from_disk(self):
        """Scan the download directory (recursively) for .jacktook.json files
        and register or update any downloads in the registry. This ensures
        that downloads started before the window was opened, or organized
        into subfolders, appear in the manager."""
        download_dir = _translatePath(_get_setting("download_dir"))
        if not download_dir or not os.path.isdir(download_dir):
            return

        manager = DownloadManager()
        try:
            for root, dirs, files in os.walk(download_dir):
                for filename in files:
                    if not filename.endswith(".jacktook.json"):
                        continue
                    dest_path = os.path.join(root, filename.replace(".jacktook.json", ""))
                    # Skip .part files — use the final path
                    if dest_path.endswith(".part"):
                        dest_path = dest_path[:-5]
                    meta = get_download_metadata(dest_path)
                    if not meta:
                        continue
                    status = meta.get("status", "unknown")
                    progress = meta.get("progress", 0)
                    url = meta.get("url", "")
                    name = meta.get("title", os.path.basename(dest_path))
                    # Only register non-cancelled entries
                    if status == "cancelled":
                        continue
                    entry = manager.get_entry(dest_path)
                    if entry:
                        # Update existing entry from disk
                        manager.set_status(dest_path, status)
                        manager.update_progress(
                            dest_path,
                            downloaded=meta.get("downloaded", 0),
                            speed=meta.get("speed", 0),
                            eta=meta.get("eta", 0),
                            progress=progress,
                            size=meta.get("size", 0),
                        )
                    else:
                        entry = manager.register(
                            name=name,
                            dest_path=dest_path,
                            url=url,
                        )
                        if entry:
                            manager.set_status(dest_path, status)
                            manager.update_progress(
                                dest_path,
                                downloaded=meta.get("downloaded", 0),
                                speed=meta.get("speed", 0),
                                eta=meta.get("eta", 0),
                                progress=progress,
                                size=meta.get("size", 0),
                            )
        except Exception as e:
            kodilog(f"[DownloadManagerWindow] Sync from disk error: {e}")

    def _poll_loop(self):
        last_sync = 0
        while not self._monitor.abortRequested() and not self._closed:
            xbmc.sleep(500)
            try:
                now = time.time()
                if now - last_sync >= 2:
                    self._sync_from_disk()
                    last_sync = now
                self._update_selected_properties()
                self._check_registry_changes()
            except Exception as e:
                kodilog(f"[DownloadManagerWindow] Poll error: {e}")

    def _update_selected_properties(self):
        # Always sync focused_item_id from the list's current selection
        # so the details panel reflects keyboard/gamepad navigation too
        try:
            control_list = self.getControl(14001)
            item = control_list.getSelectedItem()
            if item:
                self._focused_item_id = item.getProperty("entry_id") or self._focused_item_id
        except Exception:
            pass

        manager = DownloadManager()
        entry = manager.get_entry(self._focused_item_id) if self._focused_item_id else None
        if entry:
            self.setProperty("selected_progress", str(entry.progress))
            self.setProperty("selected_speed", bytes_to_human_readable(entry.speed) + "/s" if entry.speed else "")
            eta_secs = entry.eta
            if eta_secs and eta_secs > 0:
                eta_mins, eta_secs = divmod(eta_secs, 60)
                eta_hrs, eta_mins = divmod(eta_mins, 60)
                if eta_hrs:
                    self.setProperty("selected_eta", f"{eta_hrs}h {eta_mins}m")
                elif eta_mins:
                    self.setProperty("selected_eta", f"{eta_mins}m {eta_secs}s")
                else:
                    self.setProperty("selected_eta", f"{eta_secs}s")
            else:
                self.setProperty("selected_eta", "")
            self.setProperty("selected_size", bytes_to_human_readable(entry.size) if entry.size else "")
            self.setProperty("selected_downloaded", bytes_to_human_readable(entry.downloaded) if entry.downloaded else "")
            self.setProperty("selected_status", entry.status)
            self.setProperty("selected_name", entry.name)
        else:
            self.setProperty("selected_progress", "")
            self.setProperty("selected_speed", "")
            self.setProperty("selected_eta", "")
            self.setProperty("selected_size", "")
            self.setProperty("selected_downloaded", "")
            self.setProperty("selected_status", "")
            self.setProperty("selected_name", "")

    def _check_registry_changes(self):
        manager = DownloadManager()
        entries = manager.list_entries()
        checksum = ",".join(f"{e.id}:{e.status}:{e.progress}" for e in entries)
        if checksum != self._last_registry_checksum:
            self._last_registry_checksum = checksum
            execute_builtin("SendClick(14000,14002)")

    def _rebuild_list(self):
        try:
            manager = DownloadManager()
            entries = manager.list_entries()
            control_list = self.getControl(14001)
            selected_position = control_list.getSelectedPosition()
            control_list.reset()

            if not entries:
                self.setProperty("downloads_empty", "true")
                return

            self.setProperty("downloads_empty", "false")
            for entry in entries:
                label = entry.name
                speed_str = bytes_to_human_readable(entry.speed) + "/s" if entry.speed else ""
                if entry.eta and entry.eta > 0:
                    eta_mins, eta_secs = divmod(entry.eta, 60)
                    eta_hrs, eta_mins = divmod(eta_mins, 60)
                    if eta_hrs:
                        eta_str = f"{eta_hrs}h {eta_mins}m"
                    elif eta_mins:
                        eta_str = f"{eta_mins}m {eta_secs}s"
                    else:
                        eta_str = f"{eta_secs}s"
                else:
                    eta_str = ""
                size_str = bytes_to_human_readable(entry.size) if entry.size else ""
                downloaded_str = bytes_to_human_readable(entry.downloaded) if entry.downloaded else ""

                # Build secondary info line
                parts = []
                if entry.status == "completed":
                    status_str = translation(90811)  # "Completed"
                elif speed_str:
                    parts.append(speed_str)
                if eta_str and entry.status != "completed":
                    parts.append(eta_str)
                if downloaded_str and size_str:
                    parts.append(f"{downloaded_str} / {size_str}")
                elif size_str:
                    parts.append(size_str)

                info_line = " • ".join(parts)

                item = xbmcgui.ListItem(label=label)
                item.setProperty("entry_id", entry.id)
                item.setProperty("entry_name", entry.name)
                item.setProperty("entry_status", entry.status)
                item.setProperty("entry_progress", str(entry.progress))
                item.setProperty("entry_speed", speed_str)
                item.setProperty("entry_eta", eta_str)
                item.setProperty("entry_size", size_str)
                item.setProperty("entry_downloaded", downloaded_str)
                item.setProperty("entry_info", info_line)
                control_list.addItem(item)

            if 0 <= selected_position < control_list.size():
                control_list.selectItem(selected_position)

            # Set focus on the list so navigation works immediately
            self.setFocus(control_list)

            # Default focus to first entry if no previous selection
            if self._focused_item_id is None and entries:
                self._focused_item_id = entries[0].id
        except Exception as e:
            kodilog(f"[DownloadManagerWindow] Rebuild list error: {e}")

    def onAction(self, action):
        action_id = action.getId()
        if action_id in self.action_exitkeys_id:
            self._closed = True
        super().onAction(action)

    def onClick(self, control_id):
        if control_id == 14002:
            self._rebuild_list()
            return

        if control_id == 14008:
            self._closed = True
            self.close()
            return

        if control_id == 14007:
            self._clear_completed()
            execute_builtin("SendClick(14000,14002)")
            return

        if control_id not in (14003, 14004, 14005, 14006):
            return

        try:
            control_list = self.getControl(14001)
            item = control_list.getSelectedItem()
            if not item:
                return
            entry_id = item.getProperty("entry_id")
            if not entry_id:
                return
        except Exception:
            return

        self._focused_item_id = entry_id

        if control_id == 14003:
            self._pause_download(entry_id)
        elif control_id == 14004:
            self._resume_download(entry_id)
        elif control_id == 14005:
            self._cancel_download(entry_id)
        elif control_id == 14006:
            self._delete_download(entry_id)

        execute_builtin("SendClick(14000,14002)")

    def _pause_download(self, entry_id):
        manager = DownloadManager()
        entry = manager.get_entry(entry_id)
        if entry and entry.status == "downloading":
            entry.cancel_flag = True
            manager.set_status(entry_id, "paused")
            import json
            handle_pause_download({"file_path": json.dumps(entry_id)}, refresh=False)

    def _resume_download(self, entry_id):
        manager = DownloadManager()
        entry = manager.get_entry(entry_id)
        if entry and entry.status == "paused":
            import json
            import os
            dest_path = entry_id
            # Clear the cancel flag left by the pause operation
            cancel_flag_cache.set(dest_path, False)
            entry.cancel_flag = False
            meta = get_download_metadata(dest_path)
            manager.set_status(entry_id, "downloading")
            manager.update_progress(
                entry_id,
                downloaded=meta.get("downloaded", 0),
                speed=0,
                eta=0,
                progress=meta.get("progress", 0),
                size=meta.get("size", 0),
            )
            downloader = Downloader(
                url=meta.get("url", entry.url),
                destination=os.path.dirname(dest_path),
                name=os.path.basename(dest_path),
                registry_id=dest_path,
                show_progress=False,
            )
            downloader.run()

    def _cancel_download(self, entry_id):
        manager = DownloadManager()
        entry = manager.get_entry(entry_id)
        if not entry:
            return

        # Cancel works for both downloading and paused states
        entry.cancel_flag = True
        cancel_flag_cache.set(entry_id, True)
        manager.set_status(entry_id, "cancelled")

        # Update metadata on disk so a cancelled download doesn't resume on restart
        meta_path = entry_id + ".jacktook.json"
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r") as f:
                    meta = json.load(f)
                meta["status"] = "cancelled"
                with open(meta_path, "w") as f:
                    json.dump(meta, f)
            except Exception:
                pass

        # Delete the .part file (partial download) to free disk space
        temp_path = entry_id + ".part"
        if xbmcvfs.exists(temp_path):
            xbmcvfs.delete(temp_path)

    def _delete_download(self, entry_id):
        manager = DownloadManager()
        entry = manager.get_entry(entry_id)
        if not entry:
            return

        dialog = xbmcgui.Dialog()
        if not dialog.yesno(translation(90809), translation(90810)):
            return

        # Delete files
        if xbmcvfs.exists(entry_id):
            xbmcvfs.delete(entry_id)
        temp_path = entry_id + ".part"
        if xbmcvfs.exists(temp_path):
            xbmcvfs.delete(temp_path)
        meta_path = entry_id + ".jacktook.json"
        if xbmcvfs.exists(meta_path):
            xbmcvfs.delete(meta_path)

        manager.remove_entry(entry_id)

    def _clear_completed(self):
        manager = DownloadManager()
        for entry in list(manager.list_entries()):
            if entry.status == "completed":
                manager.remove_entry(entry.id)

    def handle_action(self, action_id, control_id=None):
        pass
