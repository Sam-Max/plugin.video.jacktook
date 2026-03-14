from unittest.mock import patch

from lib import navigation


def test_trakt_group_menu_renders_tv_library_group():
    with patch("lib.navigation.render_menu") as render_menu, patch(
        "lib.navigation.set_pluging_category"
    ) as set_category, patch("lib.navigation.translation", return_value="Trakt Library"):
        navigation.trakt_group_menu({"mode": "tv", "group": "library"})

    set_category.assert_called_once_with("Trakt Library")
    items = render_menu.call_args.args[0]
    assert items
    assert all(item["action"] == "search_item" for item in items)
    assert render_menu.call_args.kwargs["cache"] is False


def test_trakt_group_menu_renders_movie_discovery_group():
    with patch("lib.navigation.render_menu") as render_menu, patch(
        "lib.navigation.set_pluging_category"
    ) as set_category, patch("lib.navigation.translation", return_value="Trakt Discovery"):
        navigation.trakt_group_menu({"mode": "movies", "group": "discovery"})

    set_category.assert_called_once_with("Trakt Discovery")
    items = render_menu.call_args.args[0]
    assert items
    assert all(item["params"]["api"] == "trakt" for item in items)
    assert render_menu.call_args.kwargs["cache"] is False
