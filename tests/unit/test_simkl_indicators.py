from unittest.mock import MagicMock

import requests

from lib.api.simkl import SimklClient
from lib.utils import simkl_indicators


class FakeListItem:
    def __init__(self, label, properties):
        self.label = label
        self.properties = properties

    def getLabel(self):
        return self.label

    def setLabel(self, label):
        self.label = label

    def getProperty(self, key):
        return self.properties.get(key, "")


def _item(label, media_type, tmdb_id, season=None, episode=None):
    properties = {
        simkl_indicators.SIMKL_MEDIA_TYPE: media_type,
        simkl_indicators.SIMKL_TMDB_ID: str(tmdb_id),
    }
    if season is not None:
        properties[simkl_indicators.SIMKL_SEASON] = str(season)
        properties[simkl_indicators.SIMKL_EPISODE] = str(episode)
    return FakeListItem(label, properties)


def test_watched_lookup_uses_authenticated_bounded_payload(monkeypatch):
    response = MagicMock(status_code=200)
    response.json.return_value = []
    post = MagicMock(return_value=response)
    monkeypatch.setattr("lib.api.simkl.requests.post", post)
    client = SimklClient("client-id", "token")

    assert client.get_watched([("movie", 1), ("show", 2), ("episode", 2, 0, 3)]) == []
    post.assert_called_once_with(
        "https://api.simkl.com/sync/watched",
        params=dict(client._params, extended="counters"),
        headers=client._headers,
        json=[
            {"movie": {"ids": {"tmdb": 1}}},
            {"show": {"ids": {"tmdb": 2}}},
            {"show": {"ids": {"tmdb": 2}}, "episode": {"season": 0, "number": 3}},
        ],
        timeout=5,
    )
    assert client.get_watched([("movie", number) for number in range(101)]) == []
    assert post.call_count == 1


def test_watched_lookup_contains_transport_and_malformed_responses(monkeypatch):
    post = MagicMock(side_effect=requests.Timeout())
    monkeypatch.setattr("lib.api.simkl.requests.post", post)

    assert SimklClient("client-id", "token").get_watched([("movie", 1)]) == []
    monkeypatch.setattr("lib.api.simkl.get_setting", lambda _key: "")
    assert SimklClient("client-id", "").get_watched([("movie", 1)]) == []
    assert post.call_count == 1


def test_get_indicators_gates_auth_and_chunks_at_api_limit(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(simkl_indicators, "is_simkl_authenticated", lambda: False)
    assert simkl_indicators.get_indicators([("movie", 1)], client) == {}
    client.get_watched.assert_not_called()

    monkeypatch.setattr(simkl_indicators, "is_simkl_authenticated", lambda: True)
    client.get_watched.return_value = []
    descriptors = [("movie", number) for number in range(1, 202)]
    assert simkl_indicators.get_indicators(descriptors, client) == {}
    assert [len(call.args[0]) for call in client.get_watched.call_args_list] == [100, 100, 1]


def test_apply_indicators_uses_valid_matching_movie_show_and_episode_responses(monkeypatch):
    movie = _item("Movie", "movie", 1)
    show = _item("Show", "show", 2)
    episode = _item("Episode", "episode", 2, season=1, episode=3)
    get_watched = MagicMock(
        return_value=[
            {"movie": {"ids": {"tmdb": 1}}, "result": True, "status": "completed"},
            {
                "show": {"ids": {"tmdb": 2}},
                "result": False,
                "status": "watching",
                "counters": {"episodes_watched": 3, "episodes_aired": 10},
            },
            {
                "show": {"ids": {"tmdb": 2}},
                "episode": {"season": 1, "number": 3},
                "result": True,
                "status": "watching",
            },
        ]
    )
    monkeypatch.setattr(simkl_indicators, "is_simkl_authenticated", lambda: True)
    monkeypatch.setattr(simkl_indicators.SimklClient, "get_watched", get_watched)
    monkeypatch.setattr(
        simkl_indicators,
        "translation",
        lambda value: {90985: "Completed", 90984: "Watching", 3067: "Watched"}[value],
    )

    simkl_indicators.apply_simkl_indicators(
        [("movie", movie, False), ("show", show, True), ("episode", episode, False)]
    )

    assert movie.label == "[COLOR gray][Completed][/COLOR] Movie"
    assert show.label == "[COLOR gray][Watching | 3/10][/COLOR] Show"
    assert episode.label == "[COLOR gray][Watched][/COLOR] Episode"
    get_watched.assert_called_once_with([("movie", 1), ("show", 2), ("episode", 2, 1, 3)])


def test_apply_indicators_skips_client_for_batches_without_descriptors(monkeypatch):
    get_watched = MagicMock()
    monkeypatch.setattr(simkl_indicators, "is_simkl_authenticated", lambda: True)
    monkeypatch.setattr(simkl_indicators.SimklClient, "get_watched", get_watched)

    simkl_indicators.apply_simkl_indicators([("directory", FakeListItem("Menu", {}), True)])

    get_watched.assert_not_called()


def test_malformed_or_ambiguous_responses_do_not_change_items(monkeypatch):
    item = _item("Movie", "movie", 1)
    get_watched = MagicMock(
        return_value=[
            {"movie": {"ids": {"tmdb": 2}}, "result": True, "status": "completed"},
            {"movie": {"ids": {"tmdb": 1}}, "result": True, "status": "unknown"},
            {"movie": {"ids": {"tmdb": 1}}, "result": True, "status": "completed"},
            {"movie": {"ids": {"tmdb": 1}}, "result": False, "status": "completed"},
        ]
    )
    monkeypatch.setattr(simkl_indicators, "is_simkl_authenticated", lambda: True)
    monkeypatch.setattr(simkl_indicators.SimklClient, "get_watched", get_watched)

    simkl_indicators.apply_simkl_indicators([("movie", item, False)])

    assert item.label == "Movie"
