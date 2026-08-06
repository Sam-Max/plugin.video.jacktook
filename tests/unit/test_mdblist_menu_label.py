import importlib
from unittest.mock import patch

from lib.utils.general import items_menus


def test_mdblist_menu_entries_use_the_mdblist_label():
    with patch(
        "lib.utils.kodi.utils.translation", side_effect=lambda string_id: f"label-{string_id}"
    ):
        menus = importlib.reload(items_menus)
        for menu_items in (menus.tv_items, menus.movie_items):
            mdblist_item = next(item for item in menu_items if item.get("api") == "mdblist")
            assert mdblist_item["name"] == "label-90962"

    importlib.reload(items_menus)
