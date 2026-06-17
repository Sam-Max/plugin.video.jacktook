import json
from unittest.mock import MagicMock, patch


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
        self,
        mock_get_addons,
        mock_cache,
        mock_listitem,
        mock_dialog_cls,
        mock_get_setting,
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
        def setting_side_effect(key):
            if key == "external_scraper_module_name":
                return None
            return True

        mock_get_setting.side_effect = setting_side_effect
        mock_cache.get.return_value = None
        mock_dialog = MagicMock()
        # User selects first and third items
        mock_dialog.multiselect.return_value = [0, 2]
        mock_dialog_cls.return_value = mock_dialog

        from lib.gui.source_manager_dialog import open_source_manager_dialog

        open_source_manager_dialog()

        # cache.set is called twice to initialize defaults and twice to
        # persist the user's final selection (selection + known keys).
        assert mock_cache.set.call_count == 4
        saved_calls = {
            call.args[0]: json.loads(call.args[1]) for call in mock_cache.set.call_args_list[-2:]
        }
        assert saved_calls["source_manager_selection"] == ["Jackett", "Burst"]
        assert saved_calls["source_manager_known_keys"] == [
            "Jackett",
            "Prowlarr",
            "Burst",
            "Jackgram",
            "Easynews",
            "External Scraper",
        ]

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
        self,
        mock_get_addons,
        mock_cache,
        mock_listitem,
        mock_dialog_cls,
        mock_get_setting,
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
        # Default selection and known keys should be saved to cache
        assert mock_cache.set.call_count == 2
        saved_keys = {call.args[0] for call in mock_cache.set.call_args_list}
        assert "source_manager_selection" in saved_keys
        assert "source_manager_known_keys" in saved_keys

    @patch("lib.gui.source_manager_dialog.get_setting")
    @patch("lib.gui.source_manager_dialog.xbmcgui.Dialog")
    @patch("lib.gui.source_manager_dialog.xbmcgui.ListItem")
    @patch("lib.gui.source_manager_dialog.cache")
    def test_newly_enabled_source_is_auto_selected(
        self, mock_cache, mock_listitem, mock_dialog_cls, mock_get_setting
    ):
        """A source enabled in settings but missing from known keys should be auto-selected."""

        def setting_side_effect(key):
            return key in ("jackett_enabled", "prowlarr_enabled")

        mock_get_setting.side_effect = setting_side_effect

        def cache_get_side_effect(key):
            if key == "source_manager_selection":
                return json.dumps(["Jackett"])
            if key == "source_manager_known_keys":
                return json.dumps(["Jackett"])
            return None

        mock_cache.get.side_effect = cache_get_side_effect
        mock_dialog = MagicMock()
        mock_dialog.multiselect.return_value = None
        mock_dialog_cls.return_value = mock_dialog

        from lib.gui.source_manager_dialog import open_source_manager_dialog

        open_source_manager_dialog()

        preselect = mock_dialog.multiselect.call_args[1]["preselect"]
        # Jackett (index 0) and Prowlarr (index 1) should both be preselected
        assert preselect == [0, 1]
        # Updated selection and known keys should be saved to cache
        assert mock_cache.set.call_count == 2
        saved_calls = {
            call.args[0]: json.loads(call.args[1]) for call in mock_cache.set.call_args_list
        }
        assert "Jackett" in saved_calls["source_manager_selection"]
        assert "Prowlarr" in saved_calls["source_manager_selection"]

    @patch("lib.gui.source_manager_dialog.get_setting")
    @patch("lib.gui.source_manager_dialog.xbmcgui.Dialog")
    @patch("lib.gui.source_manager_dialog.xbmcgui.ListItem")
    @patch("lib.gui.source_manager_dialog.cache")
    def test_deselected_source_stays_deselected(
        self, mock_cache, mock_listitem, mock_dialog_cls, mock_get_setting
    ):
        """A source deliberately deselected by the user must not be re-selected on reopen."""

        def setting_side_effect(key):
            return key in ("jackett_enabled", "prowlarr_enabled")

        mock_get_setting.side_effect = setting_side_effect

        def cache_get_side_effect(key):
            if key == "source_manager_selection":
                # User previously deselected Prowlarr
                return json.dumps(["Jackett"])
            if key == "source_manager_known_keys":
                # Prowlarr was already known at the time of the last save
                return json.dumps(["Jackett", "Prowlarr"])
            return None

        mock_cache.get.side_effect = cache_get_side_effect
        mock_dialog = MagicMock()
        mock_dialog.multiselect.return_value = None
        mock_dialog_cls.return_value = mock_dialog

        from lib.gui.source_manager_dialog import open_source_manager_dialog

        open_source_manager_dialog()

        preselect = mock_dialog.multiselect.call_args[1]["preselect"]
        # Only Jackett (index 0) should be preselected
        assert preselect == [0]
        # Cache must not be modified because nothing newly enabled appeared
        mock_cache.set.assert_not_called()
