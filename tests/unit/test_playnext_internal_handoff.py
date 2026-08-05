import sys
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def fresh_player_module(monkeypatch):
    import lib
    import xbmc

    class FakeKodiPlayer:
        def __init__(self, *args, **kwargs):
            pass

    original_player_module = sys.modules.get("lib.player")

    monkeypatch.setattr(xbmc, "Player", FakeKodiPlayer)
    sys.modules.pop("lib.player", None)
    if hasattr(lib, "player"):
        delattr(lib, "player")

    try:
        yield
    finally:
        sys.modules.pop("lib.player", None)
        if hasattr(lib, "player"):
            delattr(lib, "player")

        if original_player_module is not None:
            sys.modules["lib.player"] = original_player_module
            setattr(lib, "player", original_player_module)


def _play_video_player():
    from lib.player import JacktookPLayer

    player = object.__new__(JacktookPLayer)
    player.url = "plugin://plugin.video.elementum/play?episode=4"
    player.data = {}
    player._check_volume = MagicMock(return_value=True)
    player.cancel_playback = MagicMock()
    player._handle_trakt_scrobble = MagicMock()
    player.handle_subtitles = MagicMock()
    player.monitor = MagicMock()
    player.run_error = MagicMock()
    player.play = MagicMock()
    return player


def test_internal_playnext_handoff_uses_player_play(monkeypatch):
    player = _play_video_player()
    player.data["direct_playback_handoff"] = True
    list_item = MagicMock()
    set_resolved_url = MagicMock()

    monkeypatch.setattr("lib.player.close_busy_dialog", lambda: None)
    monkeypatch.setattr("lib.player.setResolvedUrl", set_resolved_url)

    player.play_video(list_item)

    player.play.assert_called_once_with(player.url, list_item)
    set_resolved_url.assert_not_called()
    player.monitor.assert_called_once_with()


def test_normal_plugin_playback_keeps_setresolvedurl(monkeypatch):
    from lib.player import ADDON_HANDLE

    player = _play_video_player()
    list_item = MagicMock()
    set_resolved_url = MagicMock()

    monkeypatch.setattr("lib.player.close_busy_dialog", lambda: None)
    monkeypatch.setattr("lib.player.setResolvedUrl", set_resolved_url)

    player.play_video(list_item)

    set_resolved_url.assert_called_once_with(ADDON_HANDLE, True, list_item)
    player.play.assert_not_called()
    player.monitor.assert_called_once_with()


def test_queue_drain_marks_resolved_data_as_internal_handoff(monkeypatch):
    import lib.player as player_module

    original_player_class = player_module.JacktookPLayer
    original_data = {
        "url": "plugin://plugin.video.elementum/play?episode=4",
        "title": "Show",
        "mode": "tv",
    }

    class FakeNextPlayer:
        _nextep_queue = [{"data": original_data, "results": None}]
        created = []

        def __init__(self):
            self.run = MagicMock()
            self.__class__.created.append(self)

    owner = object.__new__(original_player_class)
    owner.PLAYLIST = MagicMock()

    monkeypatch.setattr(player_module, "JacktookPLayer", FakeNextPlayer)
    monkeypatch.setattr(
        "lib.utils.kodi.settings.auto_play_enabled", lambda: False
    )

    assert original_player_class._drain_nextep_queue(owner) is True

    assert len(FakeNextPlayer.created) == 1
    handoff_data = FakeNextPlayer.created[0].run.call_args.kwargs["data"]
    assert handoff_data["direct_playback_handoff"] is True
    assert handoff_data["url"] == original_data["url"]
    assert "direct_playback_handoff" not in original_data
