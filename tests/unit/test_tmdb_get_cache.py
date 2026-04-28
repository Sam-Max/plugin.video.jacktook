from unittest.mock import MagicMock, patch

from lib.clients.tmdb.utils.utils import tmdb_get


def test_tmdb_get_includes_language_in_cache_key():
    with patch("lib.clients.tmdb.utils.utils.cache") as mock_cache:
        mock_cache.get.return_value = None
        with patch(
            "lib.clients.tmdb.utils.utils.TMDb"
        ) as mock_tmdb_cls:
            mock_tmdb_instance = MagicMock()
            mock_tmdb_instance.language = "ro-RO"
            mock_tmdb_cls.return_value = mock_tmdb_instance
            with patch(
                "lib.clients.tmdb.utils.utils.Search"
            ) as mock_search_cls:
                mock_search_cls.return_value.tv_shows.return_value = {
                    "results": []
                }
                tmdb_get("search_tv", {"query": "test"})
                get_call = mock_cache.get.call_args
                assert get_call[1]["key"].endswith("|ro-RO")
                assert get_call[1]["key"].startswith("search_tv|")


def test_tmdb_get_cache_set_uses_same_language_key():
    with patch("lib.clients.tmdb.utils.utils.cache") as mock_cache:
        mock_cache.get.return_value = None
        with patch(
            "lib.clients.tmdb.utils.utils.TMDb"
        ) as mock_tmdb_cls:
            mock_tmdb_instance = MagicMock()
            mock_tmdb_instance.language = "de-DE"
            mock_tmdb_cls.return_value = mock_tmdb_instance
            with patch(
                "lib.clients.tmdb.utils.utils.Search"
            ) as mock_search_cls:
                mock_search_cls.return_value.movies.return_value = {
                    "results": []
                }
                tmdb_get("search_movie", {"query": "film"})
                set_call = mock_cache.set.call_args
                assert set_call[1]["key"].endswith("|de-DE")
                assert set_call[1]["key"].startswith("search_movie|")
