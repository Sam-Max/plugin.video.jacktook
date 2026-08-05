import json
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


def test_matching_session_consumes_next_action(monkeypatch):
    from lib.player import JacktookPLayer

    player = object.__new__(JacktookPLayer)
    player.playback_session_id = "owner-session"
    clear_property = MagicMock()

    monkeypatch.setattr(
        "lib.player.get_property",
        lambda key: json.dumps(
            {"action": "next_episode", "session_id": "owner-session"}
        ),
    )
    monkeypatch.setattr("lib.player.clear_property", clear_property)

    assert player._consume_next_dialog_action() is True
    clear_property.assert_called_once_with("jacktook_next_dialog_action")


def test_non_owner_does_not_consume_next_action(monkeypatch):
    from lib.player import JacktookPLayer

    player = object.__new__(JacktookPLayer)
    player.playback_session_id = "old-session"
    clear_property = MagicMock()

    monkeypatch.setattr(
        "lib.player.get_property",
        lambda key: json.dumps(
            {"action": "next_episode", "session_id": "current-session"}
        ),
    )
    monkeypatch.setattr("lib.player.clear_property", clear_property)

    assert player._consume_next_dialog_action() is False
    clear_property.assert_not_called()


def test_superseded_run_does_not_drain_shared_queue(monkeypatch):
    from lib.player import JacktookPLayer

    player = object.__new__(JacktookPLayer)
    player.PLAYLIST = MagicMock()
    player.clear_playback_properties = MagicMock()
    player._activate_playback_session = MagicMock()
    player._is_trakt_tracking_excluded = MagicMock(return_value=True)
    player.mark_watched = MagicMock()
    player._drain_nextep_queue = MagicMock()

    def set_constants(data):
        player.data = data
        player.url = data["url"]
        player._was_superseded = False

    def play_video(_list_item):
        player._was_superseded = True

    player.set_constants = set_constants
    player.play_video = play_video

    monkeypatch.setattr("lib.player.close_busy_dialog", lambda: None)
    monkeypatch.setattr("lib.player.make_listing", lambda data: MagicMock())

    player.run({"url": "plugin://plugin.video.elementum/play", "mode": "tv"})

    player._drain_nextep_queue.assert_not_called()


def test_dialog_handoff_contains_playback_session(monkeypatch):
    from lib.gui import custom_dialogs

    class FakeWindow:
        action = "next_episode"

        def __init__(self, *args, **kwargs):
            pass

        def doModal(self):
            pass

    custom_dialogs.PLAYLIST = MagicMock()
    custom_dialogs.PLAYLIST.size.return_value = 0
    set_property = MagicMock()

    monkeypatch.setattr(custom_dialogs, "PlayNext", FakeWindow)
    monkeypatch.setattr(custom_dialogs, "sleep", lambda milliseconds: None)
    monkeypatch.setattr(custom_dialogs, "set_property", set_property)

    custom_dialogs.run_next_dialog(
        {
            "item_info": json.dumps(
                {"playback_session_id": "owner-session"}
            )
        }
    )

    key, raw_payload = set_property.call_args.args
    assert key == "jacktook_next_dialog_action"
    assert json.loads(raw_payload) == {
        "action": "next_episode",
        "session_id": "owner-session",
    }
