from unittest.mock import MagicMock, patch

from lib.nav import library_history


def test_history_menu_renders_history_items():
    with patch("lib.nav.library_history.set_pluging_category") as set_category, patch(
        "lib.nav.library_history.add_directory_items_batch"
    ) as add_directory_items_batch, patch("lib.nav.library_history.end_of_directory"), patch(
        "lib.nav.library_history.build_url", side_effect=lambda action, **kwargs: action
    ), patch(
        "lib.nav.library_history.build_list_item",
        side_effect=lambda label, *_args, **_kwargs: label,
    ):
        library_history.history_menu({})

    set_category.assert_called_once()
    assert add_directory_items_batch.called


def test_clear_history_delegates_and_notifies():
    with patch("lib.nav.library_history.clear_history_by_type") as clear_history, patch(
        "lib.nav.library_history.notification"
    ) as notify, patch("lib.nav.library_history.translation", return_value="done"):
        library_history.clear_history({"type": "movies"})

    clear_history.assert_called_once_with(type="movies")
    notify.assert_called_once_with("done")


def test_direct_search_history_context_menu_opens_source_manager():
    search_item = MagicMock()
    history_item = MagicMock()
    clear_item = MagicMock()

    with patch("lib.nav.library_history.cache.get_list", return_value=[("direct", "Demo")]), patch(
        "lib.nav.library_history.make_list_item",
        side_effect=[search_item, history_item, clear_item],
    ), patch("lib.nav.library_history.set_pluging_category"), patch(
        "lib.nav.library_history.show_keyboard", return_value=""
    ), patch("lib.nav.library_history.addDirectoryItem"), patch(
        "lib.nav.library_history.endOfDirectory"
    ), patch("lib.nav.library_history.apply_section_view"), patch(
        "lib.nav.library_history.translation", side_effect=lambda value: f"t-{value}"
    ):
        library_history.search_direct({"mode": "direct"})

    context_menu = history_item.addContextMenuItems.call_args.args[0]
    assert (
        "t-90755",
        "RunPlugin(plugin://plugin.video.jacktook/?action=source_manager_toggle)",
    ) in context_menu
