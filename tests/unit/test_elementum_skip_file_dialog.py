from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest


def _query(url: str):
    return parse_qs(urlparse(url).query)


def test_elementum_exact_tv_episode_disables_manual_file_dialog():
    from lib.utils.player import utils

    with patch.object(utils, "is_elementum_addon", return_value=True):
        url = utils.get_elementum_url(
            "magnet:?xt=urn:btih:SEASONPACK",
            "",
            "tv",
            {"tmdb_id": "2190"},
            data={
                "title": "A TV Show",
                "tv_data": {"season": 2, "episode": 1},
            },
        )

    query = _query(url)

    assert query["show"] == ["2190"]
    assert query["season"] == ["2"]
    assert query["episode"] == ["1"]
    assert query["skip_file_dialog"] == ["true"]


@pytest.mark.parametrize(
    ("ids", "tv_data"),
    [
        ({"tmdb_id": "2190"}, {"season": 2}),
        ({"tmdb_id": "2190"}, {"season": 2, "episode": None}),
        ({}, {"season": 2, "episode": 1}),
    ],
)
def test_elementum_incomplete_tv_metadata_keeps_existing_fallback(ids, tv_data):
    from lib.utils.player import utils

    with patch.object(utils, "is_elementum_addon", return_value=True):
        url = utils.get_elementum_url(
            "magnet:?xt=urn:btih:EPISODE",
            "",
            "tv",
            ids,
            data={"title": "A TV Show", "tv_data": tv_data},
        )

    query = _query(url)

    assert "skip_file_dialog" not in query
    assert "show" not in query
    assert "season" not in query
    assert "episode" not in query


def test_elementum_movie_does_not_disable_manual_file_dialog():
    from lib.utils.player import utils

    with patch.object(utils, "is_elementum_addon", return_value=True):
        url = utils.get_elementum_url(
            "magnet:?xt=urn:btih:MOVIEPACK",
            "",
            "movies",
            {"tmdb_id": "4271"},
            data={
                "title": "Mais où est donc passée la 7ème compagnie ?",
            },
        )

    query = _query(url)

    assert "file_match" in query
    assert "skip_file_dialog" not in query
