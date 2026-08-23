import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import xbmc


def _load_real_player_module(monkeypatch):
    """Load lib/player.py with a real xbmc.Player base class.

    tests/conftest.py mocks the whole xbmc module, which makes xbmc.Player a
    MagicMock. JacktookPLayer needs a real class as its base for this unit test.
    """

    class PlayerStub:
        pass

    monkeypatch.setattr(xbmc, "Player", PlayerStub)

    player_path = Path(__file__).resolve().parents[2] / "lib" / "player.py"
    spec = importlib.util.spec_from_file_location(
        "_jacktook_player_resolution_test",
        player_path,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load lib/player.py")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_player_callback_marks_failed_playback_resolution(monkeypatch):
    player_module = _load_real_player_module(monkeypatch)
    JacktookPLayer = player_module.JacktookPLayer

    player = object.__new__(JacktookPLayer)
    player._playback_error_detected = False

    JacktookPLayer.onPlayBackError(player)

    assert player._playback_error_detected is True


def test_source_select_clears_resolving_after_failed_resolution():
    from lib.gui.source_select import SourceSelect

    window = object.__new__(SourceSelect)
    window.resolved = False
    window.item_information = {}
    window.setProperty = MagicMock()

    resolver = MagicMock()
    resolver.doModal.return_value = False

    with patch(
        "lib.gui.source_select.ResolverWindow",
        return_value=resolver,
    ):
        SourceSelect._resolve_item(
            window,
            selected_source=MagicMock(),
            pack_select=False,
        )

    assert window.resolved is False
    window.setProperty.assert_any_call("resolving", "true")
    window.setProperty.assert_any_call("resolving", "false")


def test_elementum_url_is_scoped_to_current_playback_session(monkeypatch):
    player_module = _load_real_player_module(monkeypatch)
    JacktookPLayer = player_module.JacktookPLayer

    player = object.__new__(JacktookPLayer)
    player.playback_session_id = "new-session"
    player.url = (
        "plugin://plugin.video.elementum/play"
        "?uri=magnet%3A%3Fxt%3Durn%3Abtih%3ATEST"
        "&type=tv"
        "&jacktook_session=old-session"
    )
    player.data = {"url": player.url}

    JacktookPLayer._scope_elementum_resolution_signal(player)

    assert "jacktook_session=new-session" in player.url
    assert "old-session" not in player.url
    assert player.data["url"] == player.url


def test_playback_failure_callback_keeps_parent_dialogs_open(monkeypatch):
    player_module = _load_real_player_module(monkeypatch)
    JacktookPLayer = player_module.JacktookPLayer

    player = object.__new__(JacktookPLayer)
    player.on_error = MagicMock()
    player.kill_dialog = MagicMock()
    player.stop = MagicMock()

    JacktookPLayer.handle_playback_failure(player)

    player.on_error.assert_called_once_with()
    player.kill_dialog.assert_not_called()
    player.stop.assert_called_once_with()


def test_playback_failure_without_callback_keeps_legacy_dialog_cleanup(monkeypatch):
    player_module = _load_real_player_module(monkeypatch)
    JacktookPLayer = player_module.JacktookPLayer

    player = object.__new__(JacktookPLayer)
    player.on_error = None
    player.kill_dialog = MagicMock()
    player.stop = MagicMock()

    JacktookPLayer.handle_playback_failure(player)

    player.kill_dialog.assert_called_once_with()
    player.stop.assert_called_once_with()


def test_elementum_scope_clears_only_current_session_signal(monkeypatch):
    player_module = _load_real_player_module(monkeypatch)
    JacktookPLayer = player_module.JacktookPLayer

    clear_property = MagicMock()
    monkeypatch.setattr(player_module, "clear_property", clear_property)

    player = object.__new__(JacktookPLayer)
    player.playback_session_id = "session-two"
    player.url = (
        "plugin://plugin.video.elementum/play"
        "?uri=magnet%3A%3Fxt%3Durn%3Abtih%3ATEST"
    )
    player.data = {"url": player.url}

    JacktookPLayer._scope_elementum_resolution_signal(player)

    clear_property.assert_called_once_with(
        "jacktook.elementum_resolution_failure.session-two"
    )


def test_source_select_backgrounds_do_not_fade_while_resolving():
    import re

    xml = (
        Path(__file__).resolve().parents[2]
        / "resources"
        / "skins"
        / "Default"
        / "1080i"
        / "source_select.xml"
    ).read_text()

    resolving_fades = re.findall(
        r'<animation[^>]*effect="fade"[^>]*'
        r'condition="String\.IsEqual'
        r'\(Window\(\)\.Property\(resolving\),true\)"'
        r'[^>]*>Conditional</animation>',
        xml,
    )

    assert resolving_fades == []
