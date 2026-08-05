from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest


def _query(url: str):
    return parse_qs(urlparse(url).query)


def test_elementum_client_forwards_episode_metadata():
    from lib.utils.general.utils import Players
    from lib.utils.player import utils

    ids = {"tmdb_id": "2190"}
    data = {
        "mode": "tv",
        "ids": ids,
        "tv_data": {"season": 4, "episode": 3},
    }

    with patch.object(utils, "is_elementum_addon", return_value=True):
        url = utils.get_torrent_url_for_client(
            "magnet:?xt=urn:btih:EPISODEHASH",
            "",
            "tv",
            ids,
            client=Players.ELEMENTUM,
            data=data,
        )

    query = _query(url)
    assert query["tmdb"] == ["2190"]
    assert query["show"] == ["2190"]
    assert query["season"] == ["4"]
    assert query["episode"] == ["3"]


def test_elementum_movie_omits_episode_metadata():
    from lib.utils.player import utils

    with patch.object(utils, "is_elementum_addon", return_value=True):
        url = utils.get_elementum_url(
            "magnet:?xt=urn:btih:MOVIEHASH",
            "",
            "movie",
            {"tmdb_id": "100"},
            data={"tv_data": {"season": 4, "episode": 3}},
        )

    query = _query(url)
    assert query["tmdb"] == ["100"]
    assert "show" not in query
    assert "season" not in query
    assert "episode" not in query


@pytest.mark.parametrize(
    ("ids", "data"),
    [
        ({"tmdb_id": "2190"}, {}),
        ({"tmdb_id": "2190"}, {"tv_data": {}}),
        ({"tmdb_id": "2190"}, {"tv_data": {"season": 4}}),
        ({"tmdb_id": "2190"}, {"tv_data": {"episode": 3}}),
        ({"tmdb_id": "2190"}, {"tv_data": {"season": "four", "episode": 3}}),
        ({"tmdb_id": "2190"}, {"tv_data": {"season": True, "episode": 3}}),
        ({"tmdb_id": "show"}, {"tv_data": {"season": 4, "episode": 3}}),
        ({"tmdb_id": "2190"}, {"tv_data": [4, 3]}),
    ],
)
def test_elementum_omits_invalid_or_incomplete_episode_metadata(ids, data):
    from lib.utils.player import utils

    with patch.object(utils, "is_elementum_addon", return_value=True):
        url = utils.get_elementum_url(
            "magnet:?xt=urn:btih:EPISODEHASH",
            "",
            "tv",
            ids,
            data=data,
        )

    query = _query(url)
    assert "show" not in query
    assert "season" not in query
    assert "episode" not in query
