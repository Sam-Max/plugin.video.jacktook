from concurrent.futures import Future
from unittest.mock import MagicMock, patch

from lib.gui.search_status_window import SearchStatusWindow, SearchTask, SearchTaskManager


def test_task_manager_snapshot_tasks_returns_copied_task_state():
    manager = SearchTaskManager(MagicMock())
    future = Future()
    task = SearchTask(
        name="Jackett",
        indexer_key="Jackett",
        status="Completed",
        result_count=3,
        error="",
        future=future,
    )
    manager.tasks.append(task)

    snapshots = manager.snapshot_tasks()
    snapshots[0].status = "Failed"

    assert snapshots[0].name == "Jackett"
    assert snapshots[0].result_count == 3
    assert manager.tasks[0].status == "Completed"


def test_search_status_window_on_init_does_not_start_background_gui_thread():
    manager = MagicMock()
    manager.snapshot_tasks.return_value = [
        SearchTask(name="Jackett", indexer_key="Jackett", status="Pending")
    ]
    window = SearchStatusWindow("search_status.xml", "/tmp", task_manager=manager)
    progress_control = MagicMock()
    label_control = MagicMock()

    def get_control(control_id):
        return label_control if control_id == 13001 else progress_control

    window.getControl = MagicMock(side_effect=get_control)
    window.setProperty = MagicMock()

    with patch("lib.gui.search_status_window.threading.Thread") as thread_mock:
        window.onInit()

    thread_mock.assert_not_called()
    label_control.setLabel.assert_called_once()
    window.setProperty.assert_any_call("task_0_name", "Jackett")


def test_search_status_window_poll_loop_closes_from_caller_thread_when_complete():
    manager = MagicMock()
    manager.is_complete = True
    manager.is_cancelled = False
    manager.snapshot_tasks.return_value = [
        SearchTask(name="Jackett", indexer_key="Jackett", status="Completed", result_count=2)
    ]
    window = SearchStatusWindow("search_status.xml", "/tmp", task_manager=manager)
    window.setProperty = MagicMock()
    window.getControl = MagicMock(return_value=MagicMock())
    window.close = MagicMock()

    with patch("lib.gui.search_status_window.translation", side_effect=lambda label_id: f"t:{label_id}"):
        window.run_until_complete(poll_interval_ms=0, final_delay_ms=0)

    window.setProperty.assert_any_call("task_0_status", "t:90246")
    window.setProperty.assert_any_call("search_results_count", "t:902432")
    window.close.assert_called_once_with()
