from unittest.mock import MagicMock, patch
from urllib.parse import quote

from lib.nav import torrserver


def test_torznab_search_renders_playable_results():
    api = MagicMock()
    api.search_torznab.return_value = [
        {
            "Title": "Movie 4K",
            "Tracker": "Jackett",
            "Size": "4.2 GiB",
            "Magnet": "magnet:?xt=urn:btih:abc",
        },
        {"Title": "Broken", "Magnet": ""},
    ]
    item = MagicMock()

    with patch.object(torrserver, "JACKTORR_ADDON", True), patch.object(
        torrserver, "get_torrserver_api", return_value=api
    ), patch.object(torrserver, "xbmcgui") as xbmcgui_mock, patch.object(
        torrserver, "translation", side_effect=lambda value: f"label-{value}"
    ), patch.object(torrserver, "build_list_item", return_value=item), patch.object(
        torrserver, "addDirectoryItem"
    ) as add_directory_item, patch.object(
        torrserver, "get_addon_handle", return_value=7
    ), patch.object(torrserver, "end_of_directory") as end_of_directory:
        xbmcgui_mock.Dialog.return_value.input.return_value = "orrent"
        torrserver.torznab_search({})

    api.search_torznab.assert_called_once_with("orrent")
    add_directory_item.assert_called_once()
    args = add_directory_item.call_args.args
    assert args[0] == 7
    expected_url = (
        "plugin://plugin.video.jacktorr/play_magnet"
        f"?magnet={quote('magnet:?xt=urn:btih:abc')}&buffer=true&poster=&title={quote('Movie 4K')}"
    )
    assert args[1] == expected_url
    assert args[2] is item
    assert add_directory_item.call_args.kwargs.get("isFolder") is False
    item.setProperty.assert_called_once_with("IsPlayable", "true")
    end_of_directory.assert_called_once()
    api.get_settings.assert_not_called()


def test_torznab_search_shows_disabled_hint_when_server_flag_reports_disabled():
    api = MagicMock()
    api.search_torznab.return_value = []
    api.get_settings.return_value = {"EnableTorznabSearch": False}

    with patch.object(torrserver, "JACKTORR_ADDON", True), patch.object(
        torrserver, "get_torrserver_api", return_value=api
    ), patch.object(torrserver, "xbmcgui") as xbmcgui_mock, patch.object(
        torrserver, "translation", side_effect=lambda value: f"label-{value}"
    ), patch.object(torrserver, "notification") as notification_mock, patch.object(
        torrserver, "end_of_directory"
    ), patch.object(torrserver, "get_addon_handle", return_value=7):
        xbmcgui_mock.Dialog.return_value.input.return_value = "torrent"
        torrserver.torznab_search({})

    notification_mock.assert_called_once_with("label-91067")


def test_torznab_search_shows_no_results_when_hint_unavailable():
    api = MagicMock()
    api.search_torznab.return_value = []
    api.get_settings.side_effect = RuntimeError("boom")

    with patch.object(torrserver, "JACKTORR_ADDON", True), patch.object(
        torrserver, "get_torrserver_api", return_value=api
    ), patch.object(torrserver, "xbmcgui") as xbmcgui_mock, patch.object(
        torrserver, "translation", side_effect=lambda value: f"label-{value}"
    ), patch.object(torrserver, "notification") as notification_mock, patch.object(
        torrserver, "end_of_directory"
    ), patch.object(torrserver, "get_addon_handle", return_value=7):
        xbmcgui_mock.Dialog.return_value.input.return_value = "torrent"
        torrserver.torznab_search({})

    notification_mock.assert_called_once_with("label-91066")


def test_torznab_search_cancelled_input_does_not_query():
    api = MagicMock()

    with patch.object(torrserver, "JACKTORR_ADDON", True), patch.object(
        torrserver, "get_torrserver_api", return_value=api
    ), patch.object(torrserver, "xbmcgui") as xbmcgui_mock, patch.object(
        torrserver, "end_of_directory"
    ) as end_of_directory, patch.object(torrserver, "get_addon_handle", return_value=7):
        xbmcgui_mock.Dialog.return_value.input.return_value = ""
        torrserver.torznab_search({})

    api.search_torznab.assert_not_called()
    end_of_directory.assert_called_once()


def test_torznab_search_without_jacktorr_addon_notifies():
    with patch.object(torrserver, "JACKTORR_ADDON", False), patch.object(
        torrserver, "notification"
    ) as notification_mock, patch.object(
        torrserver, "end_of_directory"
    ) as end_of_directory, patch.object(torrserver, "get_torrserver_api") as get_api, patch.object(
        torrserver, "get_addon_handle", return_value=7
    ):
        torrserver.torznab_search({})

    get_api.assert_not_called()
    notification_mock.assert_called_once()
    end_of_directory.assert_called_once()


def test_torznab_search_without_torrserver_api_notifies():
    with patch.object(torrserver, "JACKTORR_ADDON", True), patch.object(
        torrserver, "get_torrserver_api", return_value=None
    ), patch.object(torrserver, "notification") as notification_mock, patch.object(
        torrserver, "end_of_directory"
    ) as end_of_directory, patch.object(torrserver, "xbmcgui") as xbmcgui_mock:
        torrserver.torznab_search({})

    notification_mock.assert_called_once()
    end_of_directory.assert_called_once()
    xbmcgui_mock.Dialog.return_value.input.assert_not_called()
