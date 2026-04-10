from unittest.mock import patch

from lib.nav import library_history


def test_history_menu_renders_history_items():
    with patch("lib.nav.library_history.set_pluging_category") as set_category, patch(
        "lib.nav.library_history.add_directory_items_batch"
    ) as add_directory_items_batch, patch(
        "lib.nav.library_history.end_of_directory"
    ), patch(
        "lib.nav.library_history.build_url", side_effect=lambda action, **kwargs: action
    ), patch(
        "lib.nav.library_history.build_list_item", side_effect=lambda label, *_args, **_kwargs: label
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
