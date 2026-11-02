from unittest.mock import patch

from lib.clients.tmdb.tmdb import TmdbClient


def _show(seasons, number_of_seasons=1):
    return {
        "id": 100,
        "external_ids": {"imdb_id": "tt1", "tvdb_id": 2},
        "number_of_seasons": number_of_seasons,
        "seasons": seasons,
    }


def _run(tmdb_obj, include_specials):
    with patch("lib.clients.tmdb.tmdb.get_setting", return_value=include_specials):
        with patch.object(TmdbClient, "show_episodes_details") as episodes:
            with patch.object(TmdbClient, "show_seasons_details") as seasons:
                TmdbClient._show_tmdb_shows(tmdb_obj, "tv", "Title", 100, "tv")
    return episodes, seasons


def test_single_season_with_specials_opens_season_list_when_enabled():
    show = _show([{"season_number": 0, "episode_count": 6}, {"season_number": 1}])

    episodes, seasons = _run(show, include_specials=True)

    seasons.assert_called_once()
    episodes.assert_not_called()


def test_single_season_with_specials_opens_episodes_when_disabled():
    show = _show([{"season_number": 0, "episode_count": 6}, {"season_number": 1}])

    episodes, seasons = _run(show, include_specials=False)

    episodes.assert_called_once()
    assert episodes.call_args.kwargs["season"] == 1
    seasons.assert_not_called()


def test_single_season_without_specials_opens_episodes():
    show = _show([{"season_number": 1}])

    episodes, seasons = _run(show, include_specials=True)

    episodes.assert_called_once()
    assert episodes.call_args.kwargs["season"] == 1
    seasons.assert_not_called()


def test_empty_specials_season_does_not_force_season_list():
    show = _show([{"season_number": 0, "episode_count": 0}, {"season_number": 1}])

    episodes, seasons = _run(show, include_specials=True)

    episodes.assert_called_once()
    seasons.assert_not_called()


def test_multiple_seasons_opens_season_list():
    show = _show([{"season_number": 0}, {"season_number": 1}, {"season_number": 2}])

    episodes, seasons = _run(show, include_specials=False)

    seasons.assert_called_once()
    episodes.assert_not_called()


def test_missing_season_list_falls_back_to_number_of_seasons():
    show = _show([], number_of_seasons=1)

    episodes, seasons = _run(show, include_specials=True)

    episodes.assert_called_once()
    assert episodes.call_args.kwargs["season"] == 1
    seasons.assert_not_called()
