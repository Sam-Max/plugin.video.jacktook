import re
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest


def _query(url: str):
    return parse_qs(urlparse(url).query)


def test_elementum_movie_forwards_conservative_file_match():
    from lib.utils.general.utils import Players
    from lib.utils.player import utils

    ids = {"tmdb_id": "4271"}
    data = {
        "mode": "movies",
        "ids": ids,
        "title": "Mais où est donc passée la 7ème compagnie ?",
    }

    with patch.object(utils, "is_elementum_addon", return_value=True):
        url = utils.get_torrent_url_for_client(
            "magnet:?xt=urn:btih:TRILOGYHASH",
            "",
            "movies",
            ids,
            client=Players.ELEMENTUM,
            data=data,
        )

    query = _query(url)
    assert query["tmdb"] == ["4271"]
    assert "file_match" in query

    file_match = query["file_match"][0]
    assert re.search(
        file_match,
        "Mais.ou.est.donc.passee.la.7eme.compagnie.1973.1080p.mkv",
        flags=re.IGNORECASE,
    )
    assert re.search(
        file_match,
        "Mais où est donc passée la 7ème compagnie (1973).mkv",
        flags=re.IGNORECASE,
    )


def test_elementum_movie_match_does_not_match_other_trilogy_films():
    from lib.utils.player import utils

    with patch.object(utils, "is_elementum_addon", return_value=True):
        url = utils.get_elementum_url(
            "magnet:?xt=urn:btih:TRILOGYHASH",
            "",
            "movie",
            {"tmdb_id": "4271"},
            data={"title": "Mais où est donc passée la 7ème compagnie ?"},
        )

    file_match = _query(url)["file_match"][0]
    assert not re.search(
        file_match,
        "On.a.retrouve.la.7eme.compagnie.1975.1080p.mkv",
        flags=re.IGNORECASE,
    )
    assert not re.search(
        file_match,
        "La.7eme.compagnie.au.clair.de.lune.1977.1080p.mkv",
        flags=re.IGNORECASE,
    )


@pytest.mark.parametrize("title", [None, "", "Alien", "It 2", 123])
def test_elementum_movie_ambiguous_title_keeps_manual_file_picker(title):
    from lib.utils.player import utils

    with patch.object(utils, "is_elementum_addon", return_value=True):
        url = utils.get_elementum_url(
            "magnet:?xt=urn:btih:MOVIEHASH",
            "",
            "movie",
            {"tmdb_id": "100"},
            data={"title": title},
        )

    assert "file_match" not in _query(url)


def test_elementum_tv_episode_selection_does_not_add_movie_file_match():
    from lib.utils.player import utils

    with patch.object(utils, "is_elementum_addon", return_value=True):
        url = utils.get_elementum_url(
            "magnet:?xt=urn:btih:EPISODEHASH",
            "",
            "tv",
            {"tmdb_id": "2190"},
            data={
                "title": "A TV Show",
                "tv_data": {"season": 4, "episode": 3},
            },
        )

    query = _query(url)
    assert query["show"] == ["2190"]
    assert query["season"] == ["4"]
    assert query["episode"] == ["3"]
    assert "file_match" not in query
