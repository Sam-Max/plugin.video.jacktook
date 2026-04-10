from lib.router import _is_tmdb_action


def test_is_tmdb_action_includes_tmdb_search_modes():
    assert _is_tmdb_action("tmdb_search_modes") is True
