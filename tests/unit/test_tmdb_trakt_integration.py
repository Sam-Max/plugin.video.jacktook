from unittest.mock import MagicMock, patch

from lib.clients.tmdb.base import BaseTmdbClient


def test_movie_item_adds_trakt_context_actions_when_authenticated():
    list_item = MagicMock()
    ids = {"tmdb_id": 10, "imdb_id": "tt0010", "tvdb_id": ""}

    with patch("lib.clients.tmdb.base.add_tmdb_movie_context_menu", return_value=[("tmdb", "cmd")]), patch(
        "lib.clients.tmdb.base.is_trakt_auth", return_value=True
    ), patch(
        "lib.clients.tmdb.base.add_trakt_watchlist_context_menu", return_value=[("watchlist", "cmd")]
    ), patch(
        "lib.clients.tmdb.base.add_trakt_watched_context_menu", return_value=[("watched", "cmd")]
    ), patch(
        "lib.clients.tmdb.base.add_trakt_collection_context_menu", return_value=[("collection", "cmd")]
    ), patch("lib.clients.tmdb.base.add_kodi_dir_item"):
        BaseTmdbClient.add_media_directory_item(list_item, "movies", "Demo Movie", ids)

    list_item.addContextMenuItems.assert_called_once_with(
        [("tmdb", "cmd"), ("watchlist", "cmd"), ("watched", "cmd"), ("collection", "cmd")]
    )
    list_item.setProperty.assert_called_once_with("IsPlayable", "true")


def test_tv_item_skips_trakt_context_actions_when_not_authenticated():
    list_item = MagicMock()
    ids = {"tmdb_id": 20, "imdb_id": "tt0020", "tvdb_id": 200}

    with patch("lib.clients.tmdb.base.add_tmdb_show_context_menu", return_value=[("tmdb-tv", "cmd")]), patch(
        "lib.clients.tmdb.base.is_trakt_auth", return_value=False
    ), patch("lib.clients.tmdb.base.add_kodi_dir_item"):
        BaseTmdbClient.add_media_directory_item(list_item, "tv", "Demo Show", ids)

    list_item.addContextMenuItems.assert_called_once_with([("tmdb-tv", "cmd")])
