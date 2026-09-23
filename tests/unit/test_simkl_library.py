from unittest.mock import MagicMock

import pytest
import requests

from lib.api.simkl import SimklClient


def test_library_statuses_enforce_simkl_media_eligibility():
    assert SimklClient.allowed_library_statuses("movies") == ("plantowatch", "completed", "dropped")
    assert SimklClient.allowed_library_statuses("shows") == (
        "plantowatch",
        "watching",
        "completed",
        "hold",
        "dropped",
    )
    assert SimklClient.allowed_library_statuses("tv") == ()


def test_get_library_items_uses_authenticated_full_endpoint_and_skips_bad_entries(monkeypatch):
    response = MagicMock(status_code=200)
    response.json.return_value = [
        {"movie": {"title": "Movie", "ids": {"tmdb": "42"}}},
        {"movie": {"title": "No ID", "ids": {}}},
        {"movie": {"title": "Bad ID", "ids": {"tmdb": False}}},
        {"show": {"title": "Wrong Type", "ids": {"tmdb": 1}}},
        "not-an-item",
    ]
    get = MagicMock(return_value=response)
    monkeypatch.setattr("lib.api.simkl.requests.get", get)
    client = SimklClient("client-id", "token")

    assert client.get_library_items("movies", "plantowatch") == [
        {
            "query": "Movie",
            "mode": "movies",
            "media_type": "movie",
            "ids": {"tmdb_id": 42},
            "simkl_status": "plantowatch",
        }
    ]
    get.assert_called_once_with(
        "https://api.simkl.com/sync/all-items/movies/plantowatch",
        params=client._params,
        headers=client._headers,
        timeout=5,
    )


def test_get_library_items_blocks_invalid_requests_and_contains_failures(monkeypatch):
    get = MagicMock(side_effect=requests.Timeout())
    monkeypatch.setattr("lib.api.simkl.requests.get", get)
    monkeypatch.setattr("lib.api.simkl.get_setting", lambda _key: "")

    assert SimklClient("client-id", "token").get_library_items("movies", "watching") == []
    assert SimklClient("client-id", "").get_library_items("movies", "completed") == []
    assert SimklClient("client-id", "token").get_library_items("shows", "watching") == []
    assert get.call_count == 1


def test_get_library_items_unwraps_keyed_movie_payload(monkeypatch):
    response = MagicMock(status_code=200)
    response.json.return_value = {
        "movies": [
            {
                "status": "plantowatch",
                "movie": {
                    "title": "The Matrix",
                    "year": 1999,
                    "ids": {
                        "simkl": 26,
                        "slug": "the-matrix-1999",
                        "imdb": "tt0133093",
                        "tmdb": "603",
                    },
                },
            }
        ]
    }
    get = MagicMock(return_value=response)
    monkeypatch.setattr("lib.api.simkl.requests.get", get)
    client = SimklClient("client-id", "token")

    assert client.get_library_items("movies", "plantowatch") == [
        {
            "query": "The Matrix",
            "mode": "movies",
            "media_type": "movie",
            "ids": {"tmdb_id": 603},
            "simkl_status": "plantowatch",
        }
    ]


def test_get_library_items_unwraps_keyed_show_payload_and_parses_string_tmdb_id(monkeypatch):
    response = MagicMock(status_code=200)
    response.json.return_value = {
        "shows": [
            {
                "status": "plantowatch",
                "show": {
                    "title": "Charmed",
                    "year": 1998,
                    "ids": {
                        "simkl": 297,
                        "slug": "charmed",
                        "imdb": "tt0158552",
                        "tvdb": "70626",
                        "tmdb": "1981",
                    },
                },
            }
        ]
    }
    get = MagicMock(return_value=response)
    monkeypatch.setattr("lib.api.simkl.requests.get", get)
    client = SimklClient("client-id", "token")

    items = client.get_library_items("shows", "plantowatch")
    assert items == [
        {
            "query": "Charmed",
            "mode": "tv",
            "media_type": "tv",
            "ids": {"tmdb_id": 1981},
            "simkl_status": "plantowatch",
        }
    ]
    assert isinstance(items[0]["ids"]["tmdb_id"], int)


def test_get_library_items_returns_empty_list_for_empty_payload(monkeypatch):
    response = MagicMock(status_code=200)
    response.json.return_value = {}
    get = MagicMock(return_value=response)
    monkeypatch.setattr("lib.api.simkl.requests.get", get)
    client = SimklClient("client-id", "token")

    assert client.get_library_items("movies", "completed") == []


def test_get_library_items_returns_empty_list_when_media_key_missing(monkeypatch):
    response = MagicMock(status_code=200)
    response.json.return_value = {
        "shows": [{"status": "plantowatch", "show": {"title": "Charmed", "ids": {"tmdb": "1981"}}}]
    }
    get = MagicMock(return_value=response)
    monkeypatch.setattr("lib.api.simkl.requests.get", get)
    client = SimklClient("client-id", "token")

    assert client.get_library_items("movies", "dropped") == []


def test_get_library_items_sends_params_without_extended_full(monkeypatch):
    response = MagicMock(status_code=200)
    response.json.return_value = {}
    get = MagicMock(return_value=response)
    monkeypatch.setattr("lib.api.simkl.requests.get", get)
    client = SimklClient("client-id", "token")

    assert client.get_library_items("shows", "watching") == []
    get.assert_called_once_with(
        "https://api.simkl.com/sync/all-items/shows/watching",
        params=client._params,
        headers=client._headers,
        timeout=5,
    )
    assert "extended" not in get.call_args.kwargs["params"]


def test_move_to_library_status_sends_canonical_payload_and_returns_resolved_status(monkeypatch):
    response = MagicMock(status_code=200)
    response.json.return_value = {
        "items": [{"to": "completed", "response": {"status": "completed"}}]
    }
    post = MagicMock(return_value=response)
    monkeypatch.setattr("lib.api.simkl.requests.post", post)
    client = SimklClient("client-id", "token")

    assert client.move_to_library_status("movies", "42", "completed") == "completed"
    post.assert_called_once_with(
        "https://api.simkl.com/sync/add-to-list",
        params=client._params,
        headers=client._headers,
        json={"items": [{"ids": {"tmdb": 42}, "to": "completed"}]},
        timeout=5,
    )


def test_move_to_library_status_rejects_invalid_or_unconfirmed_results(monkeypatch):
    post = MagicMock()
    monkeypatch.setattr("lib.api.simkl.requests.post", post)
    client = SimklClient("client-id", "token")

    assert client.move_to_library_status("movies", 1, "watching") is None
    assert client.move_to_library_status("shows", False, "watching") is None
    post.assert_not_called()

    response = MagicMock(status_code=200)
    response.json.return_value = {"items": [{"to": "completed", "response": {"status": "dropped"}}]}
    post.return_value = response
    assert client.move_to_library_status("movies", 1, "completed") == "dropped"

    post.side_effect = requests.Timeout()
    assert client.move_to_library_status("movies", 1, "completed") is None


def test_simkl_library_menu_and_statuses_are_eligible_when_authenticated(monkeypatch):
    from lib.utils.views import simkl_library as view

    item = MagicMock()
    add_items = MagicMock()
    build_list_item = MagicMock(return_value=item)
    monkeypatch.setattr(view, "build_list_item", build_list_item)
    monkeypatch.setattr(view, "add_directory_items_batch", add_items)
    monkeypatch.setattr(view, "end_of_directory", MagicMock())
    monkeypatch.setattr(view, "translation", lambda value: str(value))
    monkeypatch.setattr(view, "is_simkl_authenticated", lambda: True)

    view.show_simkl_library({})
    assert build_list_item.call_count == 2
    assert all(call.args[1] == "simkl.png" for call in build_list_item.call_args_list)
    media_type_entries = add_items.call_args.args[0]
    assert {"media_type=movies", "media_type=shows"} == {
        entry[0].split("&")[-1] for entry in media_type_entries
    }
    view.end_of_directory.assert_called_once_with(cache=False)

    build_list_item.reset_mock()
    view.end_of_directory.reset_mock()
    view.show_simkl_library_statuses({"media_type": "movies"})
    entries = add_items.call_args.args[0]
    assert len(entries) == 3
    assert all("action=simkl_library_items" in entry[0] for entry in entries)
    assert all("watching" not in entry[0] and "hold" not in entry[0] for entry in entries)
    assert build_list_item.call_count == 3
    assert all(call.args[1] == "simkl.png" for call in build_list_item.call_args_list)
    view.end_of_directory.assert_called_once_with(cache=False)


def test_simkl_library_items_build_standard_tmdb_destinations_and_context_actions(monkeypatch):
    from lib.utils.views import simkl_library as view

    item = MagicMock()
    add_items = MagicMock()
    monkeypatch.setattr(view, "is_simkl_authenticated", lambda: True)
    monkeypatch.setattr(view, "make_list_item", MagicMock(return_value=item))
    monkeypatch.setattr(view, "add_directory_items_batch", add_items)
    monkeypatch.setattr(view, "setContent", MagicMock())
    monkeypatch.setattr(view, "end_of_directory", MagicMock())
    monkeypatch.setattr(view, "apply_section_view", MagicMock())
    monkeypatch.setattr(
        view, "translation", lambda value: "Move to %s" if value == 90988 else str(value)
    )
    monkeypatch.setattr(
        view.SimklClient,
        "get_library_items",
        lambda _self, _media_type, _status: [
            {
                "query": "Movie",
                "mode": "movies",
                "ids": {"tmdb_id": 42},
                "simkl_status": "plantowatch",
            }
        ],
    )
    monkeypatch.setattr(view, "tmdb_get", MagicMock(return_value=None))

    view.show_simkl_library_items({"media_type": "movies", "status": "plantowatch"})

    url, list_item, is_folder = add_items.call_args.args[0][0]
    assert "action=search" in url
    assert "tmdb_id%22%3A+42" in url
    assert is_folder is False
    actions = list_item.addContextMenuItems.call_args.args[0]
    assert len(actions) == 2
    assert all("action=simkl_move_to_status" in command for _label, command in actions)


@pytest.mark.parametrize(
    "media_type, mode, detail_endpoint",
    [
        ("movies", "movies", "movie_details"),
        ("shows", "tv", "tv_details"),
    ],
)
def test_simkl_library_items_apply_tmdb_artwork_and_keep_query_title(
    monkeypatch, media_type, mode, detail_endpoint
):
    from lib.utils.views import simkl_library as view

    list_item = MagicMock()
    add_items = MagicMock()
    details = {"title": "TMDB Title"}
    tmdb_get = MagicMock(return_value=details)
    set_media_infoTag = MagicMock(
        side_effect=lambda target, data, mode: target.getVideoInfoTag().setTitle(data["title"])
    )
    monkeypatch.setattr(view, "is_simkl_authenticated", lambda: True)
    monkeypatch.setattr(view, "make_list_item", MagicMock(return_value=list_item))
    monkeypatch.setattr(view, "add_directory_items_batch", add_items)
    monkeypatch.setattr(view, "setContent", MagicMock())
    monkeypatch.setattr(view, "end_of_directory", MagicMock())
    monkeypatch.setattr(view, "apply_section_view", MagicMock())
    monkeypatch.setattr(
        view, "translation", lambda value: "Move to %s" if value == 90988 else str(value)
    )
    monkeypatch.setattr(view, "tmdb_get", tmdb_get)
    monkeypatch.setattr(view, "set_media_infoTag", set_media_infoTag)
    monkeypatch.setattr(
        view.SimklClient,
        "get_library_items",
        lambda _self, _media_type, _status: [
            {"query": "Row Title", "mode": mode, "ids": {"tmdb_id": 42}}
        ],
    )

    view.show_simkl_library_items({"media_type": media_type, "status": "plantowatch"})

    tmdb_get.assert_called_once_with(detail_endpoint, 42)
    set_media_infoTag.assert_called_once_with(list_item, data=details, mode=mode)
    # The Simkl query title must win even though details carry a TMDB title.
    assert list_item.getVideoInfoTag().setTitle.call_args.args == ("Row Title",)


def test_simkl_library_items_degrade_to_bare_row_when_tmdb_details_fail(monkeypatch):
    from lib.utils.views import simkl_library as view

    list_item = MagicMock()
    add_items = MagicMock()
    tmdb_get = MagicMock(side_effect=RuntimeError("tmdb unavailable"))
    set_media_infoTag = MagicMock()
    monkeypatch.setattr(view, "is_simkl_authenticated", lambda: True)
    monkeypatch.setattr(view, "make_list_item", MagicMock(return_value=list_item))
    monkeypatch.setattr(view, "add_directory_items_batch", add_items)
    monkeypatch.setattr(view, "setContent", MagicMock())
    monkeypatch.setattr(view, "end_of_directory", MagicMock())
    monkeypatch.setattr(view, "apply_section_view", MagicMock())
    monkeypatch.setattr(
        view, "translation", lambda value: "Move to %s" if value == 90988 else str(value)
    )
    monkeypatch.setattr(view, "tmdb_get", tmdb_get)
    monkeypatch.setattr(view, "set_media_infoTag", set_media_infoTag)
    monkeypatch.setattr(
        view.SimklClient,
        "get_library_items",
        lambda _self, _media_type, _status: [
            {"query": "Row Title", "mode": "movies", "ids": {"tmdb_id": 42}}
        ],
    )

    view.show_simkl_library_items({"media_type": "movies", "status": "plantowatch"})

    set_media_infoTag.assert_not_called()
    url, row_item, is_folder = add_items.call_args.args[0][0]
    assert "action=search" in url
    assert is_folder is False
    assert row_item.getVideoInfoTag().setTitle.call_args.args == ("Row Title",)


def test_simkl_library_routes_close_directory_when_simkl_is_unavailable(monkeypatch):
    from lib.utils.views import simkl_library as view

    end_directory = MagicMock()
    notification = MagicMock()
    monkeypatch.setattr(view, "is_simkl_authenticated", lambda: False)
    monkeypatch.setattr(view, "end_of_directory", end_directory)
    monkeypatch.setattr(view, "notification", notification)
    monkeypatch.setattr(view, "translation", lambda value: str(value))

    view.show_simkl_library({})
    view.show_simkl_library_statuses({"media_type": "movies"})
    view.show_simkl_library_items({"media_type": "movies", "status": "plantowatch"})

    assert end_directory.call_count == 3
    assert all(call.kwargs == {"cache": False} for call in end_directory.call_args_list)
    assert notification.call_count == 3
    assert all(
        call.args == ("90997",) and call.kwargs == {"time": 3000}
        for call in notification.call_args_list
    )


def test_move_simkl_item_only_refreshes_when_simkl_confirms_target_status(monkeypatch):
    from lib.utils.views import simkl_library as view

    client = MagicMock()
    monkeypatch.setattr(view, "is_simkl_authenticated", lambda: True)
    monkeypatch.setattr(view, "SimklClient", MagicMock(return_value=client))
    notification = MagicMock()
    refresh = MagicMock()
    monkeypatch.setattr(view, "notification", notification)
    monkeypatch.setattr(view, "executebuiltin", refresh)
    monkeypatch.setattr(view, "translation", lambda value: str(value))
    params = {"media_type": "movies", "tmdb_id": "42", "status": "completed"}

    client.move_to_library_status.return_value = "dropped"
    view.move_simkl_item_to_status(params)
    refresh.assert_not_called()
    assert notification.call_args.args[0] == "90990"

    client.move_to_library_status.return_value = "completed"
    view.move_simkl_item_to_status(params)
    refresh.assert_called_once_with("Container.Refresh")
    assert notification.call_args.args[0] == "90989"
