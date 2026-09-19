"""The TV episode context menu must keep the anime marker on its rebuilt searches.

"Scrape again" (90049) and "Source Select" (90115) rebuild a search URL from the
context menu. Losing ``anime=1`` there makes ``run_search_entry`` skip the Kitsu
route and fall back to the IMDb id with the absolute episode number, which
returns no streams for long-running anime.
"""

from urllib.parse import parse_qs, urlparse

from lib.clients.tmdb.utils.utils import add_tmdb_episode_context_menu

TV_DATA = {"name": "Episode%201", "episode": 1, "season": 1}
IDS = {"tmdb_id": 94664, "imdb_id": "tt1234567"}


def _play_media_commands(menu):
    return [command for _label, command in menu if command.startswith("PlayMedia(")]


def _query(command):
    url = command[len("PlayMedia(") : -1]
    return {key: values[0] for key, values in parse_qs(urlparse(url).query).items()}


def _search_queries(menu):
    queries = [_query(command) for command in _play_media_commands(menu)]
    return [query for query in queries if query.get("action") == "search"]


def test_episode_context_menu_keeps_anime_marker_on_both_searches():
    menu = add_tmdb_episode_context_menu(
        mode="tv",
        tv_name="Demo Anime",
        tv_data=TV_DATA,
        ids=IDS,
        anime=True,
    )

    commands = _play_media_commands(menu)
    # Exactly the two rebuilt searches: "Scrape again" and "Source Select".
    assert len(commands) == 2
    assert all("anime=1" in command for command in commands)

    queries = _search_queries(menu)
    assert len(queries) == 2
    assert all(query["anime"] == "1" for query in queries)

    rescrape = next(query for query in queries if "rescrape" in query)
    force_select = next(query for query in queries if "force_select" in query)
    assert rescrape["anime"] == "1"
    assert force_select["anime"] == "1"


def test_episode_context_menu_marks_non_anime_searches_with_zero():
    menu = add_tmdb_episode_context_menu(
        mode="tv",
        tv_name="Demo Show",
        tv_data=TV_DATA,
        ids=IDS,
    )

    commands = _play_media_commands(menu)
    assert len(commands) == 2
    assert all("anime=0" in command for command in commands)

    queries = _search_queries(menu)
    assert len(queries) == 2
    assert all(query["anime"] == "0" for query in queries)
