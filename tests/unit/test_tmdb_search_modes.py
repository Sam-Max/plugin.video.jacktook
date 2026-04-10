import json
from unittest.mock import MagicMock, patch

from lib.clients.tmdb.tmdb import TmdbClient


def test_tmdb_search_modes_runs_title_year_search_for_movies():
    tmdb_obj = {
        "external_ids": {"imdb_id": "tt1375666", "tvdb_id": ""},
    }

    with patch.object(TmdbClient, "_get_tmdb_metadata", return_value=tmdb_obj), patch(
        "lib.clients.tmdb.tmdb.xbmcgui.Dialog"
    ) as dialog_cls, patch("lib.clients.tmdb.tmdb.show_keyboard", return_value="Inception Alt"), patch("lib.search.run_search_entry") as run_search_entry:
        dialog_cls.return_value.select.return_value = 0
        dialog_cls.return_value.numeric.return_value = "2010"

        TmdbClient.tmdb_search_modes(
            {
                "mode": "movies",
                "media_type": "movie",
                "tmdb_id": "27205",
                "query": "Inception",
            }
        )

    payload = run_search_entry.call_args[0][0]
    assert payload["query"] == "Inception Alt"
    assert payload["mode"] == "movies"
    assert payload["search_variant"] == "title_year"
    assert payload["year"] == "2010"
    assert payload["rescrape"] is True
    assert payload["force_select"] is True
    assert json.loads(payload["ids"]) == {
        "tmdb_id": "27205",
        "imdb_id": "tt1375666",
        "tvdb_id": "",
    }


def test_tmdb_search_modes_runs_original_title_search_for_movies():
    tmdb_obj = {
        "external_ids": {"imdb_id": "tt0245429", "tvdb_id": ""},
    }

    with patch.object(TmdbClient, "_get_tmdb_metadata", return_value=tmdb_obj), patch(
        "lib.clients.tmdb.tmdb.xbmcgui.Dialog"
    ) as dialog_cls, patch("lib.clients.tmdb.tmdb.show_keyboard", return_value="Sen to Chihiro no kamikakushi"), patch("lib.search.run_search_entry") as run_search_entry:
        dialog_cls.return_value.select.return_value = 1

        TmdbClient.tmdb_search_modes(
            {
                "mode": "movies",
                "media_type": "movie",
                "tmdb_id": "129",
                "query": "Spirited Away",
            }
        )

    payload = run_search_entry.call_args[0][0]
    assert payload["search_variant"] == "original_title"
    assert payload["query"] == "Sen to Chihiro no kamikakushi"
    assert payload["year"] == ""
    dialog_cls.return_value.numeric.assert_not_called()


def test_tmdb_search_modes_returns_early_when_dialog_cancelled():
    tmdb_obj = {
        "external_ids": {"imdb_id": "tt1375666", "tvdb_id": ""},
    }

    with patch.object(TmdbClient, "_get_tmdb_metadata", return_value=tmdb_obj), patch(
        "lib.clients.tmdb.tmdb.xbmcgui.Dialog"
    ) as dialog_cls, patch("lib.clients.tmdb.tmdb.show_keyboard", return_value="Inception"), patch("lib.search.run_search_entry") as run_search_entry:
        dialog_cls.return_value.select.return_value = -1

        TmdbClient.tmdb_search_modes(
            {
                "mode": "movies",
                "media_type": "movie",
                "tmdb_id": "27205",
                "query": "Inception",
            }
        )

    run_search_entry.assert_not_called()


def test_tmdb_search_modes_returns_early_when_year_input_cancelled():
    tmdb_obj = {
        "external_ids": {"imdb_id": "tt1375666", "tvdb_id": ""},
    }

    with patch.object(TmdbClient, "_get_tmdb_metadata", return_value=tmdb_obj), patch(
        "lib.clients.tmdb.tmdb.xbmcgui.Dialog"
    ) as dialog_cls, patch("lib.clients.tmdb.tmdb.show_keyboard", return_value="Inception"), patch("lib.search.run_search_entry") as run_search_entry:
        dialog_cls.return_value.select.return_value = 0
        dialog_cls.return_value.numeric.return_value = ""

        TmdbClient.tmdb_search_modes(
            {
                "mode": "movies",
                "media_type": "movie",
                "tmdb_id": "27205",
                "query": "Inception",
            }
        )

    run_search_entry.assert_not_called()


def test_tmdb_search_modes_rejects_invalid_manual_year():
    tmdb_obj = {
        "external_ids": {"imdb_id": "tt1375666", "tvdb_id": ""},
    }

    with patch.object(TmdbClient, "_get_tmdb_metadata", return_value=tmdb_obj), patch(
        "lib.clients.tmdb.tmdb.xbmcgui.Dialog"
    ) as dialog_cls, patch("lib.clients.tmdb.tmdb.show_keyboard", return_value="Inception"), patch("lib.clients.tmdb.tmdb.notification") as notification, patch(
        "lib.search.run_search_entry"
    ) as run_search_entry:
        dialog_cls.return_value.select.return_value = 2
        dialog_cls.return_value.numeric.return_value = "20ab"

        TmdbClient.tmdb_search_modes(
            {
                "mode": "movies",
                "media_type": "movie",
                "tmdb_id": "27205",
                "query": "Inception",
            }
        )

    notification.assert_called_once()
    run_search_entry.assert_not_called()


def test_tmdb_search_modes_returns_early_when_title_edit_cancelled():
    tmdb_obj = {
        "external_ids": {"imdb_id": "tt1375666", "tvdb_id": ""},
    }

    with patch.object(TmdbClient, "_get_tmdb_metadata", return_value=tmdb_obj), patch(
        "lib.clients.tmdb.tmdb.xbmcgui.Dialog"
    ) as dialog_cls, patch("lib.clients.tmdb.tmdb.show_keyboard", return_value=""), patch(
        "lib.search.run_search_entry"
    ) as run_search_entry:
        dialog_cls.return_value.select.return_value = 0

        TmdbClient.tmdb_search_modes(
            {
                "mode": "movies",
                "media_type": "movie",
                "tmdb_id": "27205",
                "query": "Inception",
            }
        )

    dialog_cls.return_value.numeric.assert_not_called()
    run_search_entry.assert_not_called()


def test_tmdb_episode_search_modes_runs_search_with_edited_title_season_episode():
    tmdb_obj = MagicMock()
    tmdb_obj.original_name = "Breaking Bad"

    with patch.object(TmdbClient, "_get_tmdb_metadata", return_value=tmdb_obj), patch(
        "lib.clients.tmdb.tmdb.xbmcgui.Dialog"
    ) as dialog_cls, patch("lib.clients.tmdb.tmdb.show_keyboard", return_value="Breaking Bad Alt"), patch(
        "lib.search.run_search_entry"
    ) as run_search_entry:
        dialog_cls.return_value.select.return_value = 0
        dialog_cls.return_value.numeric.side_effect = ["2", "5"]

        TmdbClient.tmdb_episode_search_modes(
            {
                "mode": "tv",
                "media_type": "tv",
                "query": "Breaking Bad",
                "ids": json.dumps({"tmdb_id": "1396", "imdb_id": "tt0903747", "tvdb_id": "81189"}),
                "tv_data": json.dumps({"name": "Episode 5", "season": 1, "episode": 5}),
            }
        )

    payload = run_search_entry.call_args[0][0]
    assert payload["query"] == "Breaking Bad Alt"
    assert payload["mode"] == "tv"
    assert payload["rescrape"] is True
    assert payload["force_select"] is True
    tv_data = json.loads(payload["tv_data"])
    assert tv_data["season"] == 2
    assert tv_data["episode"] == 5
    assert json.loads(payload["ids"]) == {
        "tmdb_id": "1396",
        "imdb_id": "tt0903747",
        "tvdb_id": "81189",
    }


def test_tmdb_episode_search_modes_runs_search_with_original_title():
    tmdb_obj = MagicMock()
    tmdb_obj.original_name = "Breaking Bad Original"

    with patch.object(TmdbClient, "_get_tmdb_metadata", return_value=tmdb_obj), patch(
        "lib.clients.tmdb.tmdb.xbmcgui.Dialog"
    ) as dialog_cls, patch("lib.clients.tmdb.tmdb.show_keyboard", return_value="Breaking Bad Original"), patch(
        "lib.search.run_search_entry"
    ) as run_search_entry:
        dialog_cls.return_value.select.return_value = 1
        dialog_cls.return_value.numeric.side_effect = ["3", "8"]

        TmdbClient.tmdb_episode_search_modes(
            {
                "mode": "tv",
                "media_type": "tv",
                "query": "Breaking Bad",
                "ids": json.dumps({"tmdb_id": "1396"}),
                "tv_data": json.dumps({"name": "Episode 5", "season": 1, "episode": 5}),
            }
        )

    payload = run_search_entry.call_args[0][0]
    assert payload["query"] == "Breaking Bad Original"
    tv_data = json.loads(payload["tv_data"])
    assert tv_data["season"] == 3
    assert tv_data["episode"] == 8


def test_tmdb_episode_search_modes_returns_early_when_selector_cancelled():
    tmdb_obj = MagicMock()
    tmdb_obj.original_name = "Breaking Bad"

    with patch.object(TmdbClient, "_get_tmdb_metadata", return_value=tmdb_obj), patch(
        "lib.clients.tmdb.tmdb.xbmcgui.Dialog"
    ) as dialog_cls, patch("lib.search.run_search_entry") as run_search_entry:
        dialog_cls.return_value.select.return_value = -1

        TmdbClient.tmdb_episode_search_modes(
            {
                "mode": "tv",
                "media_type": "tv",
                "query": "Breaking Bad",
                "ids": json.dumps({"tmdb_id": "1396"}),
                "tv_data": json.dumps({"name": "Episode 5", "season": 1, "episode": 5}),
            }
        )

    dialog_cls.return_value.numeric.assert_not_called()
    run_search_entry.assert_not_called()


def test_tmdb_episode_search_modes_returns_early_when_title_cancelled():
    tmdb_obj = MagicMock()
    tmdb_obj.original_name = "Breaking Bad"

    with patch.object(TmdbClient, "_get_tmdb_metadata", return_value=tmdb_obj), patch(
        "lib.clients.tmdb.tmdb.xbmcgui.Dialog"
    ) as dialog_cls, patch("lib.clients.tmdb.tmdb.show_keyboard", return_value=""), patch(
        "lib.search.run_search_entry"
    ) as run_search_entry:
        dialog_cls.return_value.select.return_value = 0

        TmdbClient.tmdb_episode_search_modes(
            {
                "mode": "tv",
                "media_type": "tv",
                "query": "Breaking Bad",
                "ids": json.dumps({"tmdb_id": "1396"}),
                "tv_data": json.dumps({"name": "Episode 5", "season": 1, "episode": 5}),
            }
        )

    dialog_cls.return_value.numeric.assert_not_called()
    run_search_entry.assert_not_called()


def test_tmdb_episode_search_modes_returns_early_when_season_cancelled():
    tmdb_obj = MagicMock()
    tmdb_obj.original_name = "Breaking Bad"

    with patch.object(TmdbClient, "_get_tmdb_metadata", return_value=tmdb_obj), patch(
        "lib.clients.tmdb.tmdb.xbmcgui.Dialog"
    ) as dialog_cls, patch("lib.clients.tmdb.tmdb.show_keyboard", return_value="Breaking Bad"), patch(
        "lib.search.run_search_entry"
    ) as run_search_entry:
        dialog_cls.return_value.select.return_value = 0
        dialog_cls.return_value.numeric.return_value = ""

        TmdbClient.tmdb_episode_search_modes(
            {
                "mode": "tv",
                "media_type": "tv",
                "query": "Breaking Bad",
                "ids": json.dumps({"tmdb_id": "1396"}),
                "tv_data": json.dumps({"name": "Episode 5", "season": 1, "episode": 5}),
            }
        )

    run_search_entry.assert_not_called()


def test_tmdb_episode_search_modes_rejects_invalid_season():
    tmdb_obj = MagicMock()
    tmdb_obj.original_name = "Breaking Bad"

    with patch.object(TmdbClient, "_get_tmdb_metadata", return_value=tmdb_obj), patch(
        "lib.clients.tmdb.tmdb.xbmcgui.Dialog"
    ) as dialog_cls, patch("lib.clients.tmdb.tmdb.show_keyboard", return_value="Breaking Bad"), patch(
        "lib.clients.tmdb.tmdb.notification"
    ) as notification, patch("lib.search.run_search_entry") as run_search_entry:
        dialog_cls.return_value.select.return_value = 0
        dialog_cls.return_value.numeric.return_value = "abc"

        TmdbClient.tmdb_episode_search_modes(
            {
                "mode": "tv",
                "media_type": "tv",
                "query": "Breaking Bad",
                "ids": json.dumps({"tmdb_id": "1396"}),
                "tv_data": json.dumps({"name": "Episode 5", "season": 1, "episode": 5}),
            }
        )

    notification.assert_called_once()
    run_search_entry.assert_not_called()


def test_tmdb_episode_search_modes_returns_early_for_non_tv_mode():
    with patch("lib.search.run_search_entry") as run_search_entry:
        TmdbClient.tmdb_episode_search_modes(
            {
                "mode": "movies",
                "media_type": "movie",
                "query": "Inception",
                "ids": json.dumps({"tmdb_id": "27205"}),
                "tv_data": json.dumps({}),
            }
        )

    run_search_entry.assert_not_called()
