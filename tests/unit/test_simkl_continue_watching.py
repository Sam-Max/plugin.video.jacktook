from unittest.mock import MagicMock

from lib.utils.general.items_menus import root_menu_items


def test_simkl_menu_is_visible_only_for_authenticated_accounts(monkeypatch):
    item = next(item for item in root_menu_items if item["action"] == "simkl_continue_watching")
    monkeypatch.setattr(
        "lib.utils.views.simkl_continue_watching.is_simkl_authenticated", lambda: False
    )
    assert item["condition"]() is False

    monkeypatch.setattr(
        "lib.utils.views.simkl_continue_watching.is_simkl_authenticated", lambda: True
    )
    assert item["condition"]() is True


def test_simkl_continue_watching_builds_resume_and_explicit_discard_actions(monkeypatch):
    from lib.utils.views import simkl_continue_watching as view

    item = MagicMock()
    monkeypatch.setattr(view, "make_list_item", MagicMock(return_value=item))
    add_items = MagicMock()
    monkeypatch.setattr(view, "add_directory_items_batch", add_items)
    monkeypatch.setattr(view, "setContent", MagicMock())
    monkeypatch.setattr(view, "end_of_directory", MagicMock())
    monkeypatch.setattr(view, "apply_section_view", MagicMock())
    monkeypatch.setattr(view, "set_pluging_category", MagicMock())
    monkeypatch.setattr(
        view.SimklClient,
        "get_playback",
        lambda _self: [
            {
                "query": "Movie",
                "mode": "movies",
                "media_type": "movie",
                "ids": {"tmdb_id": 1},
                "tv_data": {},
                "simkl_session_id": 9,
                "simkl_resume_progress": 50,
            }
        ],
    )

    view.show_simkl_continue_watching()

    url, list_item, is_folder = add_items.call_args.args[0][0]
    assert "action=simkl_resume" in url
    assert "simkl_session_id=9" in url
    assert is_folder is False
    assert list_item.addContextMenuItems.call_args.args[0][0][0] == "Discard Simkl Resume"


def test_discard_refreshes_only_after_successful_delete(monkeypatch):
    from lib.utils.views import simkl_continue_watching as view

    delete = MagicMock(return_value=False)
    monkeypatch.setattr(view.SimklClient, "delete_playback", delete)
    refresh = MagicMock()
    monkeypatch.setattr(view, "executebuiltin", refresh)

    view.discard_simkl_playback({"session_id": "9"})
    refresh.assert_not_called()

    delete.return_value = True
    view.discard_simkl_playback({"session_id": "9"})
    refresh.assert_called_once_with("Container.Refresh")


def test_simkl_resume_delegates_to_standard_source_search(monkeypatch):
    from lib import navigation

    run_search_entry = MagicMock()
    monkeypatch.setattr("lib.search.run_search_entry", run_search_entry)
    params = {"query": "Movie", "simkl_session_id": "9", "simkl_resume_progress": "50"}

    navigation.simkl_resume(params)

    run_search_entry.assert_called_once_with(params)
