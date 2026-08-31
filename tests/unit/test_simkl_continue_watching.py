import json
from unittest.mock import MagicMock

import pytest

from lib.utils.general.items_menus import (
    movie_items,
    root_menu_items,
    tv_items,
)


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


def test_simkl_library_is_visible_in_tv_and_movie_menus_when_unavailable(monkeypatch):
    from lib.navigation import _build_media_menu_entries

    assert not any(item.get("action") == "simkl_library" for item in root_menu_items)
    monkeypatch.setattr("lib.api.simkl.is_simkl_authenticated", lambda: False)

    for items, media_type in ((tv_items, "shows"), (movie_items, "movies")):
        menu_entries = _build_media_menu_entries(items)

        simkl_items = [
            item for item in items if item.get("action") == "simkl_library_statuses"
        ]
        simkl_menu_entries = [
            entry
            for entry in menu_entries
            if "action=simkl_library_statuses" in entry["url"]
        ]
        assert len(simkl_items) == 1
        assert simkl_items[0]["name"] != 90981
        assert len(simkl_menu_entries) == 1
        assert simkl_menu_entries[0]["name"] == simkl_items[0]["name"]
        assert simkl_items[0]["icon"] == "simkl.png"
        assert simkl_items[0]["params"] == {"media_type": media_type}
        assert "condition" not in simkl_items[0]
        assert items[items.index(simkl_items[0]) + 1]["params"]["group"] == "library"


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
    tmdb_get = MagicMock(return_value={"id": 1})
    set_media_info_tag = MagicMock()
    monkeypatch.setattr(view, "tmdb_get", tmdb_get)
    monkeypatch.setattr(view, "set_media_infoTag", set_media_info_tag)
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
    tmdb_get.assert_called_once_with("movie_details", 1)
    set_media_info_tag.assert_called_once_with(list_item, data={"id": 1}, mode="movies")
    list_item.getVideoInfoTag().setResumePoint.assert_called_once_with(0.5, 1)
    list_item.setProperty.assert_any_call("PercentPlayed", "50")
    assert list_item.addContextMenuItems.call_args.args[0][0][0] == "Discard Simkl Resume"


def test_simkl_continue_watching_uses_parent_show_tmdb_details(monkeypatch):
    from lib.utils.views import simkl_continue_watching as view

    item = MagicMock()
    monkeypatch.setattr(view, "make_list_item", MagicMock(return_value=item))
    monkeypatch.setattr(view, "add_directory_items_batch", MagicMock())
    monkeypatch.setattr(view, "setContent", MagicMock())
    monkeypatch.setattr(view, "end_of_directory", MagicMock())
    monkeypatch.setattr(view, "apply_section_view", MagicMock())
    monkeypatch.setattr(view, "set_pluging_category", MagicMock())
    tmdb_get = MagicMock(return_value={"id": 2})
    set_media_info_tag = MagicMock()
    monkeypatch.setattr(view, "tmdb_get", tmdb_get)
    monkeypatch.setattr(view, "set_media_infoTag", set_media_info_tag)
    monkeypatch.setattr(
        view.SimklClient,
        "get_playback",
        lambda _self: [
            {
                "query": "Show",
                "mode": "tv",
                "media_type": "tv",
                "ids": {"tmdb_id": 2},
                "tv_data": {"name": "Episode", "season": 2, "episode": 3},
                "simkl_session_id": 9,
                "simkl_resume_progress": 50,
            }
        ],
    )

    view.show_simkl_continue_watching()

    assert view.make_list_item.call_args.kwargs["label"] == "Show S02E03"
    tmdb_get.assert_called_once_with("tv_details", 2)
    set_media_info_tag.assert_called_once_with(item, data={"id": 2}, mode="tv")


def test_simkl_continue_watching_keeps_remote_resume_when_tmdb_metadata_is_unavailable(
    monkeypatch,
):
    from lib.utils.views import simkl_continue_watching as view

    item = MagicMock()
    monkeypatch.setattr(view, "make_list_item", MagicMock(return_value=item))
    add_items = MagicMock()
    monkeypatch.setattr(view, "add_directory_items_batch", add_items)
    monkeypatch.setattr(view, "setContent", MagicMock())
    monkeypatch.setattr(view, "end_of_directory", MagicMock())
    monkeypatch.setattr(view, "apply_section_view", MagicMock())
    monkeypatch.setattr(view, "set_pluging_category", MagicMock())
    monkeypatch.setattr(view, "tmdb_get", MagicMock(return_value=None))
    set_media_info_tag = MagicMock()
    monkeypatch.setattr(view, "set_media_infoTag", set_media_info_tag)
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
    assert is_folder is False
    assert list_item is item
    assert item.setArt.call_args.args[0] == {
        "icon": view.os.path.join(view.ADDON_PATH, "resources", "img", "magnet.png")
    }
    set_media_info_tag.assert_not_called()
    item.setProperty.assert_any_call("IsPlayable", "true")


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


def test_simkl_resume_resolves_external_ids_and_forces_rescrape(monkeypatch):
    from lib import navigation

    run_search_entry = MagicMock()
    tmdb_metadata = MagicMock(
        return_value={"external_ids": {"imdb_id": "tt7654321", "tvdb_id": 56789}}
    )
    monkeypatch.setattr("lib.search.run_search_entry", run_search_entry)
    monkeypatch.setattr(navigation.TmdbClient, "_get_tmdb_metadata", tmdb_metadata)
    params = {
        "query": "Movie",
        "mode": "movies",
        "media_type": "movie",
        "ids": json.dumps({"tmdb_id": 123}),
        "simkl_session_id": "9",
        "simkl_resume_progress": "50",
    }

    navigation.simkl_resume(params)

    tmdb_metadata.assert_called_once_with("movies", "movie", 123)
    run_search_entry.assert_called_once()
    search_params = run_search_entry.call_args.args[0]
    assert search_params["rescrape"] is True
    assert json.loads(search_params["ids"]) == {
        "tmdb_id": 123,
        "imdb_id": "tt7654321",
        "tvdb_id": 56789,
    }


@pytest.mark.parametrize(
    "tmdb_response",
    [None, RuntimeError("TMDB unavailable")],
    ids=["metadata unavailable", "TMDB request fails"],
)
def test_simkl_resume_continues_search_when_tmdb_metadata_is_unavailable(
    monkeypatch, tmdb_response
):
    from lib import navigation

    run_search_entry = MagicMock()
    tmdb_metadata = MagicMock()
    if isinstance(tmdb_response, Exception):
        tmdb_metadata.side_effect = tmdb_response
    else:
        tmdb_metadata.return_value = tmdb_response
    monkeypatch.setattr("lib.search.run_search_entry", run_search_entry)
    monkeypatch.setattr(navigation.TmdbClient, "_get_tmdb_metadata", tmdb_metadata)
    params = {
        "query": "Movie",
        "mode": "movies",
        "media_type": "movie",
        "ids": json.dumps({"tmdb_id": 123}),
        "simkl_session_id": "9",
        "simkl_resume_progress": "50",
    }

    navigation.simkl_resume(params)

    run_search_entry.assert_called_once()
    search_params = run_search_entry.call_args.args[0]
    assert search_params["query"] == "Movie"
    assert search_params["rescrape"] is True
    assert json.loads(search_params["ids"]) == {"tmdb_id": 123}
