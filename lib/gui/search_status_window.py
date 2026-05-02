from dataclasses import dataclass, field
from typing import List, Optional, Callable, Dict, Any
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
import threading

import xbmc
import xbmcgui

from lib.utils.kodi.utils import kodilog, translation
from lib.gui.base_window import BaseWindow
from lib.domain.torrent import TorrentStream


STATUS_MAP = {
    "Pending": 90244,
    "In Progress": 90245,
    "Completed": 90246,
    "Failed": 90247,
    "Cancelled": 90248,
}


@dataclass
class SearchTask:
    name: str
    indexer_key: str
    status: str = (
        "Pending"  # "Pending", "In Progress", "Completed", "Failed", "Cancelled"
    )
    result_count: int = 0
    error: str = ""
    future: Optional[Future] = None


class SearchTaskManager:
    def __init__(self, executor: ThreadPoolExecutor):
        self.executor = executor
        self.tasks: List[SearchTask] = []
        self._cancel_event = threading.Event()

    def submit_task(
        self, name: str, indexer_key: str, fn: Callable, *args, **kwargs
    ) -> SearchTask:
        task = SearchTask(name=name, indexer_key=indexer_key)
        self.tasks.append(task)

        def wrapped_fn(*a, **kw):
            if self._cancel_event.is_set():
                task.status = "Cancelled"
                return []

            task.status = "In Progress"
            try:
                # ARTIFICIAL DELAY FOR TESTING GUI UPDATES
                # xbmc.sleep(8000)

                results = fn(*a, **kw)

                if self._cancel_event.is_set():
                    task.status = "Cancelled"
                    return results if results else []

                task.status = "Completed"
                task.result_count = len(results) if results else 0
                return results
            except Exception as e:
                task.status = "Failed"
                task.error = str(e)
                kodilog(f"Task {name} failed: {e}")
                return []

        future = self.executor.submit(wrapped_fn, *args, **kwargs)
        task.future = future
        return task

    def cancel_pending(self):
        self._cancel_event.set()
        for task in self.tasks:
            if task.status in ["Pending", "In Progress"]:
                if task.future and getattr(task.future, "cancel", lambda: False)():
                    task.status = "Cancelled"

    @property
    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    @property
    def is_complete(self) -> bool:
        return all(t.status in ["Completed", "Failed", "Cancelled"] for t in self.tasks)

    def collect_results(self) -> List[TorrentStream]:
        total_results = []
        for task in self.tasks:
            if task.future and task.future.done():
                try:
                    res = task.future.result()
                    if res:
                        total_results.extend(res)
                except Exception as e:
                    kodilog(f"Error collecting result for {task.name}: {e}")
        return total_results


class SearchStatusWindow(BaseWindow):
    MAX_TASK_SLOTS = 10

    def __init__(
        self,
        xml_file: str,
        location: str,
        task_manager: SearchTaskManager,
        item_information=None,
    ):
        super().__init__(xml_file, location, item_information=item_information)
        self.task_manager = task_manager
        self._monitor = xbmc.Monitor()

    def onInit(self):
        self.getControl(13001).setLabel(translation(90241))
        self.setProperty("instant_close", "false")

        # Set initial task names so they appear immediately
        for i, task in enumerate(self.task_manager.tasks):
            if i >= self.MAX_TASK_SLOTS:
                break
            self.setProperty(f"task_{i}_name", task.name)
            self.setProperty(
                f"task_{i}_status", translation(STATUS_MAP.get(task.status, 90244))
            )
            self.setProperty(f"task_{i}_color", self._get_status_color(task.status))
            self.setProperty(f"task_{i}_results", "")
            show_spinner = "true" if task.status == "In Progress" and task.result_count == 0 else ""
            self.setProperty(f"task_{i}_show_spinner", show_spinner)

        # Start background update thread
        self._update_thread = threading.Thread(target=self._update_loop)
        self._update_thread.daemon = True
        self._update_thread.start()

    def _get_status_color(self, status: str) -> str:
        if status == "Pending":
            return "FF888888"  # Grey
        elif status == "In Progress":
            return "FFFFD700"  # Yellow
        elif status == "Completed":
            return "FF00FF00"  # Green
        elif status == "Failed":
            return "FFFF0000"  # Red
        elif status == "Cancelled":
            return "FFFFA500"  # Orange
        return "FFFFFFFF"  # White

    def _update_loop(self):
        while not self._monitor.abortRequested() and not self.task_manager.is_complete:
            xbmc.sleep(250)

            if self.task_manager.is_cancelled:
                break

            self._update_ui_state()

        # Final update
        self._update_ui_state()

        # Give user a brief moment to see final state if not cancelled
        if not self.task_manager.is_cancelled:
            xbmc.sleep(500)

        self.close()

    def _update_ui_state(self):
        total_tasks = len(self.task_manager.tasks)
        completed_tasks = 0
        total_results = 0

        for i, task in enumerate(self.task_manager.tasks):
            if i >= self.MAX_TASK_SLOTS:
                break

            status_text = translation(STATUS_MAP.get(task.status, 90244))
            self.setProperty(f"task_{i}_name", task.name)
            self.setProperty(f"task_{i}_status", status_text)
            self.setProperty(f"task_{i}_color", self._get_status_color(task.status))

            total_results += task.result_count

            if task.status == "Completed":
                completed_tasks += 1
                self.setProperty(f"task_{i}_results", str(task.result_count))
                self.setProperty(f"task_{i}_show_spinner", "")
            elif task.status in ["Failed", "Cancelled"]:
                completed_tasks += 1
                self.setProperty(f"task_{i}_results", "")
                self.setProperty(f"task_{i}_show_spinner", "")
            elif task.status == "In Progress":
                self.setProperty(
                    f"task_{i}_results",
                    str(task.result_count) if task.result_count > 0 else "",
                )
                show_spinner = "true" if task.result_count == 0 else ""
                self.setProperty(f"task_{i}_show_spinner", show_spinner)
            else:
                self.setProperty(f"task_{i}_results", "")
                self.setProperty(f"task_{i}_show_spinner", "")

        # Update progress
        if total_tasks > 0:
            percent = int((completed_tasks / total_tasks) * 100)
            self.getControl(13002).setPercent(percent)

        self.setProperty("search_results_count", f"{translation(90243)}{total_results}")

    def onAction(self, action):
        action_id = action.getId()
        if action_id in self.action_exitkeys_id:
            self.task_manager.cancel_pending()
        super().onAction(action)

    def handle_action(self, action_id, control_id=None):
        if action_id == 7 and control_id == 13004:  # Cancel button clicked
            self.task_manager.cancel_pending()
            self.close()
