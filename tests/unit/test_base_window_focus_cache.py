from unittest.mock import MagicMock, patch

from lib.gui.base_window import BaseWindow


class _DummyWindow(BaseWindow):
    def handle_action(self, action_id, control_id=None):
        return None


def test_set_cached_focus_uses_window_property_not_addon_setting():
    window = _DummyWindow("dummy.xml", "")
    window.CACHE_KEY = "focus-key"

    with patch("lib.gui.base_window.xbmcgui.Window") as xbmc_window, patch(
        "lib.gui.base_window.ADDON"
    ) as addon:
        win = xbmc_window.return_value
        win.getProperty.return_value = ""

        window.set_cached_focus(1000, 5)

    addon.setSetting.assert_not_called()
    win.setProperty.assert_called_once()
    prop_name, prop_value = win.setProperty.call_args[0]
    assert prop_name.startswith("jacktook.focus.")
    assert prop_value == "[1000, 5]"


def test_get_cached_focus_migrates_legacy_addon_setting_to_window_property():
    window = _DummyWindow("dummy.xml", "")
    window.CACHE_KEY = "legacy-focus-key"

    with patch("lib.gui.base_window.xbmcgui.Window") as xbmc_window, patch(
        "lib.gui.base_window.ADDON"
    ) as addon:
        win = xbmc_window.return_value
        win.getProperty.return_value = ""
        addon.getSetting.return_value = "[1000, 7]"

        control_id, item_id = window.get_cached_focus()

    assert control_id == 1000
    assert item_id == 7
    addon.getSetting.assert_called_once_with("legacy-focus-key")
    addon.setSetting.assert_called_once_with("legacy-focus-key", "")
    win.setProperty.assert_called_once()


def test_get_cached_focus_returns_empty_when_cache_key_missing():
    window = _DummyWindow("dummy.xml", "")
    window.CACHE_KEY = ""

    with patch("lib.gui.base_window.xbmcgui.Window") as xbmc_window, patch(
        "lib.gui.base_window.ADDON"
    ) as addon:
        control_id, item_id = window.get_cached_focus()

    assert control_id is None
    assert item_id is None
    addon.getSetting.assert_not_called()
    xbmc_window.assert_not_called()
