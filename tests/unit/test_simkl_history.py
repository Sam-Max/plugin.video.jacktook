from unittest.mock import MagicMock

import pytest
import requests

from lib.api.simkl import SimklClient
from lib.utils.simkl_context import add_simkl_history_context_menu


@pytest.mark.parametrize(
    "operation, media_type, season, episode, response_data, endpoint, payload",
    [
        (
            "add",
            "movie",
            None,
            None,
            {"added": {"movies": 1}, "not_found": {"movies": []}},
            "history",
            {"movies": [{"ids": {"tmdb": 42}}]},
        ),
        (
            "remove",
            "movie",
            None,
            None,
            {"deleted": {"movies": 1}, "not_found": {"movies": []}},
            "history/remove",
            {"movies": [{"ids": {"tmdb": 42}}]},
        ),
        (
            "add",
            "episode",
            0,
            1,
            {"added": {"episodes": 1}, "not_found": {"episodes": []}},
            "history",
            {
                "shows": [
                    {
                        "ids": {"tmdb": 42},
                        "seasons": [{"number": 0, "episodes": [{"number": 1}]}],
                    }
                ]
            },
        ),
        (
            "remove",
            "episode",
            2,
            3,
            {"deleted": {"episodes": 1}, "not_found": {"episodes": []}},
            "history/remove",
            {
                "shows": [
                    {
                        "ids": {"tmdb": 42},
                        "seasons": [{"number": 2, "episodes": [{"number": 3}]}],
                    }
                ]
            },
        ),
    ],
)
def test_update_history_uses_confirmed_canonical_movie_and_episode_payloads(
    monkeypatch, operation, media_type, season, episode, response_data, endpoint, payload
):
    response = MagicMock(status_code=200)
    response.json.return_value = response_data
    post = MagicMock(return_value=response)
    monkeypatch.setattr("lib.api.simkl.requests.post", post)
    client = SimklClient("client-id", "token")

    assert client.update_history(operation, media_type, "42", season, episode) is True
    post.assert_called_once_with(
        f"https://api.simkl.com/sync/{endpoint}",
        params=client._params,
        headers=client._headers,
        json=payload,
        timeout=5,
    )


@pytest.mark.parametrize(
    "result",
    [
        {},
        {"added": {"movies": 1}},
        {"added": {"movies": 1}, "not_found": []},
        {"added": {"movies": 1}, "not_found": {"movies": 0}},
        {"added": {"movies": 1}, "not_found": {"movies": ["movie"]}},
        {"added": {"movies": 1, "episodes": 1}, "not_found": {"movies": []}},
        {"added": {"movies": 1}, "not_found": {"movies": [], "episodes": []}},
        {"added": {"movies": True}, "not_found": {"movies": []}},
        {"added": {"movies": 2}, "not_found": {"movies": []}},
        [],
    ],
)
def test_history_change_confirmation_rejects_malformed_response_variants(result):
    assert SimklClient._history_change_confirmed(result, "add", "movie") is False


def test_update_history_rejects_invalid_not_found_malformed_and_transport_responses(monkeypatch):
    post = MagicMock()
    monkeypatch.setattr("lib.api.simkl.requests.post", post)
    client = SimklClient("client-id", "token")

    assert client.update_history("add", "episode", 42, False, 1) is False
    assert client.update_history("add", "episode", 42, 0, 0) is False
    assert post.call_count == 0

    response = MagicMock(status_code=200)
    response.json.return_value = {"deleted": {"movies": 1}, "not_found": {"movies": ["movie"]}}
    post.return_value = response
    assert client.update_history("remove", "movie", 42) is False

    response.json.return_value = {"deleted": {"movies": 2}, "not_found": {"movies": []}}
    assert client.update_history("remove", "movie", 42) is False

    response.json.side_effect = ValueError()
    assert client.update_history("remove", "movie", 42) is False

    post.side_effect = requests.Timeout()
    assert client.update_history("remove", "movie", 42) is False


def test_simkl_history_context_menu_requires_authentication_and_valid_identity(monkeypatch):
    action_url_run = MagicMock(return_value="RunPlugin(command)")
    monkeypatch.setattr("lib.utils.simkl_context.action_url_run", action_url_run)
    monkeypatch.setattr("lib.utils.simkl_context.translation", lambda value: f"label-{value}")
    monkeypatch.setattr("lib.utils.simkl_context.is_simkl_authenticated", lambda: False)

    assert add_simkl_history_context_menu("movie", 42) == []

    monkeypatch.setattr("lib.utils.simkl_context.is_simkl_authenticated", lambda: True)
    assert add_simkl_history_context_menu("movie", "bad") == []
    assert add_simkl_history_context_menu("episode", 42, False, 1) == []

    menu = add_simkl_history_context_menu("episode", "42", 0, "1")
    assert [label for label, _command in menu] == ["label-90991", "label-90992"]
    assert action_url_run.call_args_list[0].kwargs == {
        "operation": "add",
        "media_type": "episode",
        "tmdb_id": "42",
        "season": 0,
        "episode": "1",
    }


def test_history_view_requires_movie_removal_confirmation_and_refreshes_only_on_success(
    monkeypatch,
):
    from lib.utils.views import simkl_history as view

    client = MagicMock()
    notification = MagicMock()
    refresh = MagicMock()
    confirmation = MagicMock(return_value=False)
    monkeypatch.setattr(view, "is_simkl_authenticated", lambda: True)
    monkeypatch.setattr(view, "SimklClient", MagicMock(return_value=client))
    monkeypatch.setattr(view, "dialogyesno", confirmation)
    monkeypatch.setattr(view, "notification", notification)
    monkeypatch.setattr(view, "refresh", refresh)
    monkeypatch.setattr(view, "translation", lambda value: str(value))

    params = {"operation": "remove", "media_type": "movie", "tmdb_id": "42"}
    view.update_simkl_history(params)
    client.update_history.assert_not_called()
    refresh.assert_not_called()

    confirmation.return_value = True
    client.update_history.return_value = False
    view.update_simkl_history(params)
    refresh.assert_not_called()
    assert notification.call_args.args[0] == "90996"

    client.update_history.return_value = True
    view.update_simkl_history(params)
    refresh.assert_called_once()
    assert notification.call_args.args[0] == "90995"
