from unittest.mock import patch

import pytest

from lib import navigation


@pytest.mark.parametrize(
    ("mode", "enabled", "authorized"),
    [
        ("tv", False, False),
        ("movies", False, True),
        ("tv", True, False),
    ],
)
def test_trakt_library_group_notifies_and_closes_when_unavailable(mode, enabled, authorized):
    with patch("lib.navigation.get_setting", return_value=enabled), patch(
        "lib.navigation.is_trakt_auth", return_value=authorized
    ), patch("lib.navigation.notification") as notification, patch(
        "lib.navigation.end_of_directory"
    ) as end_of_directory, patch("lib.navigation.render_menu") as render_menu, patch(
        "lib.navigation.translation", return_value="Enable and authorize Trakt in settings."
    ):
        navigation.trakt_group_menu({"mode": mode, "group": "library"})

    notification.assert_called_once_with("Enable and authorize Trakt in settings.", time=3000)
    end_of_directory.assert_called_once_with(cache=False)
    render_menu.assert_not_called()


@pytest.mark.parametrize("mode", ["tv", "movies"])
def test_trakt_group_menu_renders_library_group_when_available(mode):
    with patch("lib.navigation.render_menu") as render_menu, patch(
        "lib.navigation.set_pluging_category"
    ) as set_category, patch("lib.navigation.translation", return_value="Trakt Library"), patch(
        "lib.navigation.get_setting", return_value=True
    ), patch("lib.navigation.is_trakt_auth", return_value=True):
        navigation.trakt_group_menu({"mode": mode, "group": "library"})

    set_category.assert_called_once_with("Trakt Library")
    items = render_menu.call_args.args[0]
    assert items
    assert all(item["action"] == "search_item" for item in items)
    assert render_menu.call_args.kwargs["cache"] is False


def test_trakt_group_menu_renders_movie_discovery_group():
    with patch("lib.navigation.render_menu") as render_menu, patch(
        "lib.navigation.set_pluging_category"
    ) as set_category, patch("lib.navigation.translation", return_value="Trakt Discovery"), patch(
        "lib.navigation.get_setting", return_value=False
    ), patch("lib.navigation.is_trakt_auth", return_value=False), patch(
        "lib.navigation.notification"
    ) as notification:
        navigation.trakt_group_menu({"mode": "movies", "group": "discovery"})

    set_category.assert_called_once_with("Trakt Discovery")
    items = render_menu.call_args.args[0]
    assert items
    assert all(item["params"]["api"] == "trakt" for item in items)
    assert render_menu.call_args.kwargs["cache"] is False
    notification.assert_not_called()
