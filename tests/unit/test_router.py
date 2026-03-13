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


def test_get_route_handler_falls_back_to_core_dispatcher():
    router = _load_router_module()

    assert router._get_route_handler("history_menu") is router._route_core


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
