from unittest.mock import MagicMock

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
        params=dict(client._params, extended="full"),
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


def test_simkl_library_menu_and_statuses_are_authenticated_and_eligible(monkeypatch):
    from lib.utils.views import simkl_library as view

    item = MagicMock()
    add_items = MagicMock()
    monkeypatch.setattr(view, "make_list_item", MagicMock(return_value=item))
    monkeypatch.setattr(view, "add_directory_items_batch", add_items)
    monkeypatch.setattr(view, "end_of_directory", MagicMock())
    monkeypatch.setattr(view, "translation", lambda value: str(value))
    monkeypatch.setattr(view, "is_simkl_authenticated", lambda: False)

    view.show_simkl_library({})
    add_items.assert_not_called()

    monkeypatch.setattr(view, "is_simkl_authenticated", lambda: True)
    view.show_simkl_library_statuses({"media_type": "movies"})
    entries = add_items.call_args.args[0]
    assert len(entries) == 3
    assert all("action=simkl_library_items" in entry[0] for entry in entries)
    assert all("watching" not in entry[0] and "hold" not in entry[0] for entry in entries)


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
                "ids": {"tmdb_id": 42},
                "simkl_status": "plantowatch",
            }
        ],
    )

    view.show_simkl_library_items({"media_type": "movies", "status": "plantowatch"})

    url, list_item, is_folder = add_items.call_args.args[0][0]
    assert "action=search" in url
    assert "tmdb_id%22%3A+42" in url
    assert is_folder is False
    actions = list_item.addContextMenuItems.call_args.args[0]
    assert len(actions) == 2
    assert all("action=simkl_move_to_status" in command for _label, command in actions)


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
