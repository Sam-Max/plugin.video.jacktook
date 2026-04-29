import json
from unittest.mock import MagicMock, patch

import pytest


class FakeAddon:
    def __init__(self, key, name):
        self._key = key
        self.manifest = MagicMock()
        self.manifest.name = name

    def key(self):
        return self._key

    def url(self):
        return f"http://example.com/{self._key}"


class TestOpenSourceManagerDialog:
    @patch("lib.gui.source_manager_dialog.get_setting")
    @patch("lib.gui.source_manager_dialog.xbmcgui.Dialog")
    @patch("lib.gui.source_manager_dialog.xbmcgui.ListItem")
    @patch("lib.gui.source_manager_dialog.cache")
    def test_no_sources_enabled_shows_notification(
        self, mock_cache, mock_listitem, mock_dialog_cls, mock_get_setting
    ):
        mock_get_setting.return_value = False
        mock_dialog = MagicMock()
        mock_dialog_cls.return_value = mock_dialog

        from lib.gui.source_manager_dialog import open_source_manager_dialog

        open_source_manager_dialog()

        mock_dialog.notification.assert_called_once()
        mock_dialog.multiselect.assert_not_called()

    @patch("lib.gui.source_manager_dialog.get_setting")
    @patch("lib.gui.source_manager_dialog.xbmcgui.Dialog")
    @patch("lib.gui.source_manager_dialog.xbmcgui.ListItem")
    @patch("lib.gui.source_manager_dialog.cache")
    def test_enabled_builtins_are_shown(
        self, mock_cache, mock_listitem, mock_dialog_cls, mock_get_setting
    ):
        def setting_side_effect(key):
            return key in ("jackett_enabled", "prowlarr_enabled")

        mock_get_setting.side_effect = setting_side_effect
        mock_dialog = MagicMock()
        mock_dialog.multiselect.return_value = None
        mock_dialog_cls.return_value = mock_dialog

        from lib.gui.source_manager_dialog import open_source_manager_dialog

        open_source_manager_dialog()

        calls = mock_listitem.call_args_list
        labels = [call.kwargs.get("label", call.args[0] if call.args else "") for call in calls]
        assert "Jackett" in labels
        assert "Prowlarr" in labels
        assert "Burst" not in labels
        assert "Jackgram" not in labels

    @patch("lib.gui.source_manager_dialog.get_setting")
    @patch("lib.gui.source_manager_dialog.xbmcgui.Dialog")
    @patch("lib.gui.source_manager_dialog.xbmcgui.ListItem")
    @patch("lib.gui.source_manager_dialog.cache")
    @patch(
        "lib.clients.stremio.helpers.get_selected_stream_addons",
        return_value=[
            FakeAddon("addon1|url1", "Addon One"),
            FakeAddon("addon2|url2", "Addon Two"),
        ],
    )
    def test_stremio_addons_included_when_enabled(
        self, mock_get_addons, mock_cache, mock_listitem, mock_dialog_cls, mock_get_setting
    ):
        def setting_side_effect(key):
            return key == "stremio_enabled"

        mock_get_setting.side_effect = setting_side_effect
        mock_dialog = MagicMock()
        mock_dialog.multiselect.return_value = None
        mock_dialog_cls.return_value = mock_dialog

        from lib.gui.source_manager_dialog import open_source_manager_dialog

        open_source_manager_dialog()

        calls = mock_listitem.call_args_list
        labels = [call.kwargs.get("label", call.args[0] if call.args else "") for call in calls]
        assert "Stremio" not in labels
        assert "Addon One" in labels
        assert "Addon Two" in labels

    @patch("lib.gui.source_manager_dialog.get_setting")
    @patch("lib.gui.source_manager_dialog.xbmcgui.Dialog")
    @patch("lib.gui.source_manager_dialog.xbmcgui.ListItem")
    @patch("lib.gui.source_manager_dialog.cache")
    def test_preselect_uses_cache_selection(
        self, mock_cache, mock_listitem, mock_dialog_cls, mock_get_setting
    ):
        def setting_side_effect(key):
            return key in ("jackett_enabled", "jacktookburst_enabled")

        mock_get_setting.side_effect = setting_side_effect
        mock_cache.get.return_value = json.dumps(["Jackett", "Burst"])
        mock_dialog = MagicMock()
        mock_dialog.multiselect.return_value = None
        mock_dialog_cls.return_value = mock_dialog

        from lib.gui.source_manager_dialog import open_source_manager_dialog

        open_source_manager_dialog()

        preselect = mock_dialog.multiselect.call_args[1]["preselect"]
        # Jackett is first item (index 0), Burst is second item (index 1)
        assert preselect == [0, 1]

    @patch("lib.gui.source_manager_dialog.get_setting")
    @patch("lib.gui.source_manager_dialog.xbmcgui.Dialog")
    @patch("lib.gui.source_manager_dialog.xbmcgui.ListItem")
    @patch("lib.gui.source_manager_dialog.cache")
    def test_selection_saved_to_cache(
        self, mock_cache, mock_listitem, mock_dialog_cls, mock_get_setting
    ):
        mock_get_setting.return_value = True
        mock_cache.get.return_value = None
        mock_dialog = MagicMock()
        # User selects first and third items
        mock_dialog.multiselect.return_value = [0, 2]
        mock_dialog_cls.return_value = mock_dialog

        from lib.gui.source_manager_dialog import open_source_manager_dialog

        open_source_manager_dialog()

        # cache.set is called twice:
        # 1) to initialize default "all enabled" selection when cache is empty
        # 2) to persist the user's final selection
        assert mock_cache.set.call_count == 2
        saved_key = mock_cache.set.call_args[0][0]
        saved_value = mock_cache.set.call_args[0][1]
        assert saved_key == "source_manager_selection"
        assert json.loads(saved_value) == ["Jackett", "Burst"]

    @patch("lib.gui.source_manager_dialog.get_setting")
    @patch("lib.gui.source_manager_dialog.xbmcgui.Dialog")
    @patch("lib.gui.source_manager_dialog.xbmcgui.ListItem")
    @patch("lib.gui.source_manager_dialog.cache")
    def test_cancel_does_not_modify_cache(
        self, mock_cache, mock_listitem, mock_dialog_cls, mock_get_setting
    ):
        # Seed an existing selection so the default-init path is skipped
        def setting_side_effect(key):
            return key in ("jackett_enabled", "prowlarr_enabled")

        mock_get_setting.side_effect = setting_side_effect
        mock_cache.get.return_value = json.dumps(["Jackett", "Prowlarr"])
        mock_dialog = MagicMock()
        mock_dialog.multiselect.return_value = None
        mock_dialog_cls.return_value = mock_dialog

        from lib.gui.source_manager_dialog import open_source_manager_dialog

        open_source_manager_dialog()

        mock_cache.set.assert_not_called()

    @patch("lib.gui.source_manager_dialog.get_setting")
    @patch("lib.gui.source_manager_dialog.xbmcgui.Dialog")
    @patch("lib.gui.source_manager_dialog.xbmcgui.ListItem")
    @patch("lib.gui.source_manager_dialog.cache")
    def test_empty_selection_does_not_modify_cache(
        self, mock_cache, mock_listitem, mock_dialog_cls, mock_get_setting
    ):
        # Seed an existing selection so the default-init path is skipped
        def setting_side_effect(key):
            return key in ("jackett_enabled", "prowlarr_enabled")

        mock_get_setting.side_effect = setting_side_effect
        mock_cache.get.return_value = json.dumps(["Jackett", "Prowlarr"])
        mock_dialog = MagicMock()
        mock_dialog.multiselect.return_value = []
        mock_dialog_cls.return_value = mock_dialog

        from lib.gui.source_manager_dialog import open_source_manager_dialog

        open_source_manager_dialog()

        mock_cache.set.assert_not_called()

    @patch("lib.gui.source_manager_dialog.get_setting")
    @patch("lib.gui.source_manager_dialog.xbmcgui.Dialog")
    @patch("lib.gui.source_manager_dialog.xbmcgui.ListItem")
    @patch("lib.gui.source_manager_dialog.cache")
    @patch(
        "lib.clients.stremio.helpers.get_selected_stream_addons",
        return_value=[FakeAddon("addon1|url1", "Addon One")],
    )
    def test_stremio_addon_cache_key_format(
        self, mock_get_addons, mock_cache, mock_listitem, mock_dialog_cls, mock_get_setting
    ):
        def setting_side_effect(key):
            return key == "stremio_enabled"

        mock_get_setting.side_effect = setting_side_effect
        mock_cache.get.return_value = None
        mock_dialog = MagicMock()
        # Select first addon (index 0)
        mock_dialog.multiselect.return_value = [0]
        mock_dialog_cls.return_value = mock_dialog

        from lib.gui.source_manager_dialog import open_source_manager_dialog

        open_source_manager_dialog()

        saved = json.loads(mock_cache.set.call_args[0][1])
        assert "Stremio" not in saved
        assert "Stremio:addon1|url1" in saved

    @patch("lib.gui.source_manager_dialog.get_setting")
    @patch("lib.gui.source_manager_dialog.xbmcgui.Dialog")
    @patch("lib.gui.source_manager_dialog.xbmcgui.ListItem")
    @patch("lib.gui.source_manager_dialog.cache")
    def test_empty_cache_preselects_all_enabled_sources(
        self, mock_cache, mock_listitem, mock_dialog_cls, mock_get_setting
    ):
        """When no prior selection exists, all enabled sources should be preselected."""
        def setting_side_effect(key):
            return key in ("jackett_enabled", "prowlarr_enabled")

        mock_get_setting.side_effect = setting_side_effect
        mock_cache.get.return_value = None
        mock_dialog = MagicMock()
        mock_dialog.multiselect.return_value = None
        mock_dialog_cls.return_value = mock_dialog

        from lib.gui.source_manager_dialog import open_source_manager_dialog

        open_source_manager_dialog()

        preselect = mock_dialog.multiselect.call_args[1]["preselect"]
        # Both Jackett (index 0) and Prowlarr (index 1) should be preselected
        assert preselect == [0, 1]
        # Default selection should be saved to cache
        mock_cache.set.assert_called_once()
        saved = json.loads(mock_cache.set.call_args[0][1])
        assert "Jackett" in saved
        assert "Prowlarr" in saved

    @patch("lib.gui.source_manager_dialog.get_setting")
    @patch("lib.gui.source_manager_dialog.xbmcgui.Dialog")
    @patch("lib.gui.source_manager_dialog.xbmcgui.ListItem")
    @patch("lib.gui.source_manager_dialog.cache")
    def test_newly_enabled_source_is_auto_selected(
        self, mock_cache, mock_listitem, mock_dialog_cls, mock_get_setting
    ):
        """A source enabled in settings but missing from cache should be auto-selected."""
        def setting_side_effect(key):
            return key in ("jackett_enabled", "prowlarr_enabled")

        mock_get_setting.side_effect = setting_side_effect
        # Cache only has Jackett — Prowlarr was enabled after cache was created
        mock_cache.get.return_value = json.dumps(["Jackett"])
        mock_dialog = MagicMock()
        mock_dialog.multiselect.return_value = None
        mock_dialog_cls.return_value = mock_dialog

        from lib.gui.source_manager_dialog import open_source_manager_dialog

        open_source_manager_dialog()

        preselect = mock_dialog.multiselect.call_args[1]["preselect"]
        # Jackett (index 0) and Prowlarr (index 1) should both be preselected
        assert preselect == [0, 1]
        # Updated selection should be saved to cache
        mock_cache.set.assert_called_once()
        saved = json.loads(mock_cache.set.call_args[0][1])
        assert "Jackett" in saved
        assert "Prowlarr" in saved
