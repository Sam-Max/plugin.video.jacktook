import importlib
import sys
from unittest.mock import patch


def _load_router_module():
    if "lib.router" in sys.modules:
        return importlib.reload(sys.modules["lib.router"])
    return importlib.import_module("lib.router")


def test_get_route_handler_returns_debrid_dispatcher():
    router = _load_router_module()

    assert router._get_route_handler("rd_auth") is router._route_debrid


def test_get_route_handler_returns_cache_dispatcher():
    router = _load_router_module()

    assert router._get_route_handler("clear_tmdb_cache") is router._route_cache


def test_get_route_handler_returns_download_dispatcher_for_handle_download_file():
    router = _load_router_module()

    assert router._get_route_handler("handle_download_file") is router._route_downloads


def test_get_route_handler_falls_back_to_core_dispatcher():
    router = _load_router_module()

    assert router._get_route_handler("history_menu") is router._route_core
    assert router._get_route_handler("play_trailer") is router._route_core


def test_get_route_handler_routes_settings_backup_actions_to_core_dispatcher():
    router = _load_router_module()

    assert router._get_route_handler("export_settings_backup") is router._route_core
    assert router._get_route_handler("restore_settings_backup") is router._route_core
    assert router._get_route_handler("reset_all_settings") is router._route_core
    assert router._get_route_handler("factory_reset") is router._route_core


def test_addon_router_uses_grouped_dispatcher():
    router = _load_router_module()

    with patch.object(sys, "argv", ["plugin.video.jacktook", "1", "?action=rd_auth"]), patch(
        "lib.router._route_debrid"
    ) as route_debrid, patch(
        "lib.router._get_route_handler", return_value=route_debrid
    ) as get_route_handler, patch(
        "lib.utils.tmdb_init.ensure_tmdb_init"
    ):
        router.addon_router()

    get_route_handler.assert_called_once_with("rd_auth")
    route_debrid.assert_called_once()


def test_addon_router_without_params_opens_root_menu():
    router = _load_router_module()

    with patch.object(sys, "argv", ["plugin.video.jacktook", "1", ""]), patch(
        "lib.navigation.root_menu"
    ) as root_menu:
        router.addon_router()

    root_menu.assert_called_once_with()


def test_route_trakt_dispatches_trakt_group_menu_action():
    router = _load_router_module()

    params = {"mode": "tv", "group": "library"}
    with patch("lib.navigation.trakt_group_menu") as trakt_group_menu:
        router._route_trakt("trakt_group_menu", params)

    trakt_group_menu.assert_called_once_with(params)


def test_route_downloads_dispatches_handle_download_file():
    router = _load_router_module()

    params = {"url": "https://example.com/video.mp4"}
    with patch("lib.downloader.handle_download_file") as handle_download_file:
        router._route_downloads("handle_download_file", params)

    handle_download_file.assert_called_once_with(params)


def test_get_route_handler_returns_source_manager_dispatcher():
    router = _load_router_module()

    assert router._get_route_handler("source_manager_toggle") is router._route_source_manager


def test_route_source_manager_opens_dialog():
    router = _load_router_module()

    with patch("lib.gui.source_manager_dialog.open_source_manager_dialog") as mock_dialog:
        router._route_source_manager("source_manager_toggle", {})

    mock_dialog.assert_called_once_with()
