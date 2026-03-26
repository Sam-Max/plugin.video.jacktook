from unittest.mock import MagicMock, patch

from lib.gui.skip_intro_window import SkipIntroWindow


@patch("lib.gui.skip_intro_window.Thread")
def test_on_init_starts_background_monitor_thread(mock_thread_cls):
    thread = MagicMock()
    mock_thread_cls.return_value = thread

    window = SkipIntroWindow(
        "skip_intro.xml", "", segment_data={"end_sec": 30}, label="Skip Intro"
    )
    window.setProperty = MagicMock()

    window.onInit()

    window.setProperty.assert_called_once_with("skip_label", "Skip Intro")
    mock_thread_cls.assert_called_once_with(target=window._background_monitor)
    assert window.monitor_thread is thread
    assert thread.daemon is True
    thread.start.assert_called_once_with()


def test_on_click_skip_seeks_to_segment_end():
    window = SkipIntroWindow("skip_intro.xml", "", segment_data={"end_sec": 42})
    window.player = MagicMock()
    window.player.isPlaying.return_value = True
    window.close = MagicMock()

    window.onClick(4001)

    assert window.action == "skip"
    window.player.seekTime.assert_called_once_with(42)
    window.close.assert_called_once_with()
