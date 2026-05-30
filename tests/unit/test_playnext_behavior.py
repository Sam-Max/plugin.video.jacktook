import sys
from types import ModuleType
from unittest.mock import MagicMock, call

import pytest


@pytest.fixture(autouse=True)
def import_player_with_real_xbmc_player(monkeypatch):
    import xbmc

    class FakeKodiPlayer:
        def __init__(self, *args, **kwargs):
            pass

    monkeypatch.setattr(xbmc, "Player", FakeKodiPlayer)
    sys.modules.pop("lib.player", None)
    yield
    sys.modules.pop("lib.player", None)


def _player_instance():
    from lib.player import JacktookPLayer

    player = object.__new__(JacktookPLayer)
    player.data = {
        "mode": "tv",
        "title": "Show",
        "ids": {"tmdb_id": "123"},
        "tv_data": {"season": 1, "episode": 1},
    }
    player.playnext = MagicMock()
    player.play = MagicMock()
    player.run = MagicMock()
    player.PLAYLIST = MagicMock()
    return player


def test_handle_next_dialog_action_ignores_playlist_advance_and_uses_handler(monkeypatch):
    from lib.player import JacktookPLayer

    player = _player_instance()
    player.PLAYLIST.size.return_value = 2
    player.PLAYLIST.getposition.return_value = 0
    clear_property = MagicMock()
    monkeypatch.setattr("lib.player.get_setting", lambda key, default=None: 0)
    monkeypatch.setattr("lib.player.clear_property", clear_property)
    monkeypatch.setattr(player, "_get_next_episode_data", lambda: None)

    JacktookPLayer._handle_next_dialog_action(player)

    player.playnext.assert_not_called()
    player.play.assert_not_called()
    clear_property.assert_called_once_with("jacktook_next_dialog_action")


def test_handle_next_dialog_action_still_watching_cancel_clears_and_stops(monkeypatch):
    import xbmcgui

    from lib.player import JacktookPLayer

    player = _player_instance()
    player.PLAYLIST.size.return_value = 2
    player.PLAYLIST.getposition.return_value = 0
    clear_property = MagicMock()
    set_property = MagicMock()
    dialog = MagicMock()
    dialog.yesno.return_value = False

    monkeypatch.setattr("lib.player.get_setting", lambda key, default=None: 2)
    monkeypatch.setattr("lib.player.get_property", lambda key: "2")
    monkeypatch.setattr("lib.player.clear_property", clear_property)
    monkeypatch.setattr("lib.player.set_property", set_property)
    monkeypatch.setattr(xbmcgui, "Dialog", lambda: dialog)

    JacktookPLayer._handle_next_dialog_action(player)

    player.playnext.assert_not_called()
    set_property.assert_not_called()
    assert clear_property.call_args_list == [
        call("jacktook_consecutive_autoplays"),
        call("jacktook_next_dialog_action"),
    ]


def test_check_next_dialog_time_mode_triggers_at_time_left_threshold(monkeypatch):
    from lib.player import JacktookPLayer

    player = _player_instance()
    player.total_time = 600
    player.current_time = 550
    player.watched_percentage = 91.7
    player.playback_started_properly = True
    player.next_dialog = True
    player.playing_next_time = 50
    execute_builtin = MagicMock()

    monkeypatch.setattr("lib.player.get_setting", lambda key, default=None: False)
    monkeypatch.setattr("lib.player.action_url_run", lambda **kwargs: "RunPlugin(test)")
    monkeypatch.setattr("lib.player.xbmc.executebuiltin", execute_builtin)

    JacktookPLayer.check_next_dialog(player)

    execute_builtin.assert_called_once_with("RunPlugin(test)")
    assert player.next_dialog is False


def test_check_next_dialog_passes_authoritative_next_tv_data(monkeypatch):
    from lib.player import JacktookPLayer

    player = _player_instance()
    player.data["tv_data"] = {"season": 1, "episode": 3}
    player.total_time = 600
    player.current_time = 550
    player.watched_percentage = 91.7
    player.playback_started_properly = True
    player.next_dialog = True
    player.playing_next_time = 50
    next_tv_data = {"season": 1, "episode": 4, "name": "Immediate Next"}
    captured = {}

    monkeypatch.setattr(player, "_get_next_episode_data", MagicMock(return_value=next_tv_data))
    monkeypatch.setattr("lib.player.get_setting", lambda key, default=None: False)

    def fake_action_url_run(**kwargs):
        captured.update(kwargs)
        return "RunPlugin(test)"

    execute_builtin = MagicMock()
    monkeypatch.setattr("lib.player.action_url_run", fake_action_url_run)
    monkeypatch.setattr("lib.player.xbmc.executebuiltin", execute_builtin)

    JacktookPLayer.check_next_dialog(player)

    execute_builtin.assert_called_once_with("RunPlugin(test)")
    assert captured["name"] == "run_next_dialog"
    assert captured["item_info"]["next_tv_data"] == next_tv_data
    assert player.data["next_tv_data"] == next_tv_data
    player._get_next_episode_data.assert_called_once_with()


def test_check_next_dialog_percentage_mode_triggers_at_percentage_threshold(monkeypatch):
    from lib.player import JacktookPLayer

    player = _player_instance()
    player.total_time = 600
    player.current_time = 570
    player.watched_percentage = 95.0
    player.playback_started_properly = True
    player.next_dialog = True
    player.playing_next_time = 10
    execute_builtin = MagicMock()

    def get_setting(key, default=None):
        return {"playnext_use_percentage": True, "playnext_percentage": 95}.get(key, default)

    monkeypatch.setattr("lib.player.get_setting", get_setting)
    monkeypatch.setattr("lib.player.action_url_run", lambda **kwargs: "RunPlugin(test)")
    monkeypatch.setattr("lib.player.xbmc.executebuiltin", execute_builtin)

    JacktookPLayer.check_next_dialog(player)

    execute_builtin.assert_called_once_with("RunPlugin(test)")
    assert player.next_dialog is False


def test_check_next_dialog_does_not_trigger_before_halfway_guard(monkeypatch):
    from lib.player import JacktookPLayer

    player = _player_instance()
    player.total_time = 600
    player.current_time = 299
    player.watched_percentage = 99.0
    player.playback_started_properly = True
    player.next_dialog = True
    player.playing_next_time = 400
    execute_builtin = MagicMock()

    monkeypatch.setattr("lib.player.get_setting", lambda key, default=None: True)
    monkeypatch.setattr("lib.player.xbmc.executebuiltin", execute_builtin)

    JacktookPLayer.check_next_dialog(player)

    execute_builtin.assert_not_called()
    assert player.next_dialog is True


def test_play_window_background_tasks_ignores_missing_progress_bar(monkeypatch):
    from lib.gui.play_window import PlayWindow

    class TestPlayWindow(PlayWindow):
        def smart_play_action(self):
            self.smart_play_called = True

    window = object.__new__(TestPlayWindow)
    window.closed = False
    window.playing_file = "file.mkv"
    window.smart_play_called = False
    window.getControl = MagicMock(side_effect=RuntimeError("missing"))
    window.getTotalTime = MagicMock(side_effect=[3, 1, 1])
    window.getTime = MagicMock(return_value=0)
    window.getPlayingFile = MagicMock(return_value="file.mkv")
    window.setProperty = MagicMock()
    window.close = MagicMock()
    monkeypatch.setattr("lib.gui.play_window.xbmc.sleep", MagicMock())

    window.background_tasks()

    window.close.assert_called_once_with()
    assert window.smart_play_called is True


def test_build_next_episode_properties_prefers_next_tv_data():
    from lib.gui.play_next_window import build_next_episode_properties

    properties = build_next_episode_properties(
        {
            "title": "Current Title",
            "query": "Show Name",
            "poster": "poster.jpg",
            "fanart": "fanart.jpg",
            "clearlogo": "logo.png",
            "plot": "Episode plot",
            "tv_data": {"season": 1, "episode": 1},
            "next_tv_data": {"season": "2", "episode": "3", "name": "The Next One"},
        }
    )

    assert properties["next.title"] == "Show Name"
    assert properties["next.poster"] == "poster.jpg"
    assert properties["next.fanart"] == "fanart.jpg"
    assert properties["next.clearlogo"] == "logo.png"
    assert properties["next.season"] == "2"
    assert properties["next.episode"] == "3"
    assert properties["next.episode_label"] == "S02E03"
    assert properties["next.episode_name"] == "The Next One"
    assert properties["next.plot"] == "Episode plot"


def test_build_next_episode_properties_infers_next_episode_from_tv_data():
    from lib.gui.play_next_window import build_next_episode_properties

    properties = build_next_episode_properties(
        {
            "title": "Show Name",
            "tv_data": {"season": "1", "episode": "1"},
        }
    )

    assert properties["next.title"] == "Show Name"
    assert properties["next.season"] == "1"
    assert properties["next.episode"] == "2"
    assert properties["next.episode_label"] == "S01E02"
    assert properties["next.episode_name"] == "Episode 2"


def test_build_next_episode_properties_handles_invalid_episode_data():
    from lib.gui.play_next_window import build_next_episode_properties

    properties = build_next_episode_properties(
        {
            "title": "Show Name",
            "tv_data": {"season": "one", "episode": "two"},
        }
    )

    assert properties["next.title"] == "Show Name"
    assert properties["next.season"] == ""
    assert properties["next.episode"] == ""
    assert properties["next.episode_label"] == ""
    assert properties["next.episode_name"] == ""


def test_handle_next_dialog_action_reuses_authoritative_next_tv_data(monkeypatch):
    from lib.player import JacktookPLayer

    player = _player_instance()
    player.data["tv_data"] = {"season": 1, "episode": 3}
    player.data["next_tv_data"] = {"season": 1, "episode": 4, "name": "Immediate Next"}
    recalculator = MagicMock(return_value={"season": 1, "episode": 8, "name": "Wrong Drift"})
    cache_handler = MagicMock(return_value=True)

    monkeypatch.setattr(player, "_get_next_episode_data", recalculator)
    monkeypatch.setattr(player, "_queue_from_autoscrape_cache", cache_handler)
    monkeypatch.setattr("lib.player.get_setting", lambda key, default=None: 0)
    monkeypatch.setattr("lib.player.get_property", lambda key: "")

    JacktookPLayer._handle_next_dialog_action(player)

    recalculator.assert_not_called()
    cache_handler.assert_called_once_with(
        {"season": 1, "episode": 4, "name": "Immediate Next"},
        {"tmdb_id": "123"},
    )


def test_handle_next_dialog_action_falls_back_when_authoritative_missing(monkeypatch):
    from lib.player import JacktookPLayer

    player = _player_instance()
    fallback_next = {"season": 1, "episode": 2, "name": "Fallback Next"}
    recalculator = MagicMock(return_value=fallback_next)
    cache_handler = MagicMock(return_value=True)

    monkeypatch.setattr(player, "_get_next_episode_data", recalculator)
    monkeypatch.setattr(player, "_queue_from_autoscrape_cache", cache_handler)
    monkeypatch.setattr("lib.player.get_setting", lambda key, default=None: 0)
    monkeypatch.setattr("lib.player.get_property", lambda key: "")

    JacktookPLayer._handle_next_dialog_action(player)

    recalculator.assert_called_once_with()
    cache_handler.assert_called_once_with(fallback_next, {"tmdb_id": "123"})


def test_handle_next_dialog_action_falls_back_when_authoritative_invalid(monkeypatch):
    from lib.player import JacktookPLayer

    player = _player_instance()
    player.data["next_tv_data"] = {"season": "bad", "episode": 4, "name": "Invalid"}
    fallback_next = {"season": 1, "episode": 2, "name": "Fallback Next"}
    recalculator = MagicMock(return_value=fallback_next)
    cache_handler = MagicMock(return_value=True)

    monkeypatch.setattr(player, "_get_next_episode_data", recalculator)
    monkeypatch.setattr(player, "_queue_from_autoscrape_cache", cache_handler)
    monkeypatch.setattr("lib.player.get_setting", lambda key, default=None: 0)
    monkeypatch.setattr("lib.player.get_property", lambda key: "")

    JacktookPLayer._handle_next_dialog_action(player)

    recalculator.assert_called_once_with()
    cache_handler.assert_called_once_with(fallback_next, {"tmdb_id": "123"})


def test_drain_nextep_queue_source_select_cancel_does_not_force_container_update(monkeypatch):
    from lib.player import JacktookPLayer

    player = _player_instance()
    JacktookPLayer._nextep_queue.clear()
    JacktookPLayer._nextep_queue.append(
        {
            "data": {
                "mode": "tv",
                "ids": {"tmdb_id": "123"},
                "tv_data": {"season": 1, "episode": 4},
                "query": "Show",
                "media_type": "tv",
            },
            "results": [{"name": "Source 1"}],
        }
    )
    show_source_select = MagicMock(return_value=False)
    fake_search = ModuleType("lib.search")
    fake_search.show_source_select = show_source_select
    execute_builtin = MagicMock()
    close_busy_dialog = MagicMock()
    close_all_dialog = MagicMock()
    clear_property = MagicMock()

    monkeypatch.setitem(sys.modules, "lib.search", fake_search)
    monkeypatch.setattr("lib.utils.kodi.settings.auto_play_enabled", lambda: False)
    monkeypatch.setattr("lib.player.xbmc.executebuiltin", execute_builtin)
    monkeypatch.setattr("lib.player.close_busy_dialog", close_busy_dialog)
    monkeypatch.setattr("lib.player.close_all_dialog", close_all_dialog)
    monkeypatch.setattr("lib.player.clear_property", clear_property)

    try:
        assert JacktookPLayer._drain_nextep_queue(player) is True
    finally:
        JacktookPLayer._nextep_queue.clear()

    show_source_select.assert_called_once()
    assert not any(
        call_args.args
        and isinstance(call_args.args[0], str)
        and "Container.Update" in call_args.args[0]
        for call_args in execute_builtin.call_args_list
    )
    close_busy_dialog.assert_called_once_with()
    close_all_dialog.assert_called_once_with()
    clear_property.assert_called_once_with("jacktook_next_dialog_action")
    player.PLAYLIST.clear.assert_called_once_with()


def _make_play_next(monkeypatch, auto_timeout=10):
    """Create a PlayNext instance without calling __init__ for testing."""
    from lib.gui.play_next_window import PlayNext

    window = object.__new__(PlayNext)
    window.auto_timeout = auto_timeout
    window.closed = False
    window.playing_file = "file.mkv"
    window.player = MagicMock()
    window.action = None
    window.handle_action = MagicMock()
    window.setProperty = MagicMock()
    window.close = MagicMock()
    window.doModal = MagicMock()
    window.calculate_percent = MagicMock(return_value=50.0)
    window.getControl = MagicMock(side_effect=RuntimeError("missing"))
    return window


def test_play_next_background_tasks_timeout_reached(monkeypatch):
    """Task 3.1: Countdown reaches zero triggers auto-play."""
    monkeypatch.setattr("lib.gui.play_next_window.xbmc.sleep", lambda ms: None)
    window = _make_play_next(monkeypatch, auto_timeout=3)
    window.getTotalTime = MagicMock(return_value=600)
    window.getTime = MagicMock(return_value=500)
    window.getPlayingFile = MagicMock(return_value="file.mkv")

    window.background_tasks()

    window.handle_action.assert_called_once_with(7, 3001)
    window.close.assert_called_once_with()


def test_play_next_background_tasks_episode_ended(monkeypatch):
    """Task 3.1: Episode ends (<= 2s remaining) triggers immediate auto-play."""
    monkeypatch.setattr("lib.gui.play_next_window.xbmc.sleep", lambda ms: None)
    window = _make_play_next(monkeypatch, auto_timeout=10)
    window.getTotalTime = MagicMock(return_value=600)
    window.getTime = MagicMock(return_value=598)
    window.getPlayingFile = MagicMock(return_value="file.mkv")

    window.background_tasks()

    # handle_action called, then early return (close not called directly
    # because handle_action is mocked; in production handle_action calls close)
    window.handle_action.assert_called_once_with(7, 3001)


def test_play_next_background_tasks_window_closed(monkeypatch):
    """Task 3.1: Window closed during countdown exits without auto-play."""
    monkeypatch.setattr("lib.gui.play_next_window.xbmc.sleep", lambda ms: None)
    window = _make_play_next(monkeypatch, auto_timeout=10)
    window.getTotalTime = MagicMock(return_value=600)
    window.getTime = MagicMock(return_value=500)
    window.getPlayingFile = MagicMock(return_value="file.mkv")
    window.closed = True  # Window already closed before loop starts

    window.background_tasks()

    window.handle_action.assert_not_called()
    window.close.assert_called_once_with()


def test_play_next_background_tasks_legacy_mode(monkeypatch):
    """Task 3.1: Legacy mode (timeout <= 0) uses episode-remaining timer."""
    monkeypatch.setattr("lib.gui.play_next_window.xbmc.sleep", lambda ms: None)
    # Mock smart_play_action to avoid real implementation
    monkeypatch.setattr(
        "lib.gui.play_next_window.PlayNext.smart_play_action",
        lambda self: None,
    )
    window = _make_play_next(monkeypatch, auto_timeout=0)
    # Set near end so super().background_tasks() loop exits immediately
    window.getTotalTime = MagicMock(return_value=600)
    window.getTime = MagicMock(return_value=598)
    window.getPlayingFile = MagicMock(return_value="file.mkv")

    window.background_tasks()

    window.setProperty.assert_any_call("timer_label", "Playing in {} seconds")
    window.close.assert_called_once_with()
