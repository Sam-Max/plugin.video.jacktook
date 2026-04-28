from unittest.mock import MagicMock, patch

from lib.clients.tmdb.tmdb import TmdbClient


def test_get_cached_tmdb_item_metadata_includes_language_in_cache_key():
    item = {"id": 123, "title": "Test", "media_type": "movie"}
    with patch("lib.clients.tmdb.tmdb.cache") as mock_cache:
        mock_cache.get.return_value = None
        with patch(
            "lib.clients.tmdb.tmdb.TMDb"
        ) as mock_tmdb_cls:
            mock_tmdb_instance = MagicMock()
            mock_tmdb_instance.language = "ro-RO"
            mock_tmdb_cls.return_value = mock_tmdb_instance
            with patch(
                "lib.clients.tmdb.tmdb.tmdb_get", return_value={"logos": []}
            ):
                TmdbClient._get_cached_tmdb_item_metadata(item, "movies")
                get_call = mock_cache.get.call_args
                assert get_call[0][0] == "tmdb_ui_meta|movies|123|ro-RO"


def test_get_cached_tmdb_item_metadata_cache_set_uses_same_language_key():
    item = {"id": 456, "name": "Show", "media_type": "tv"}
    with patch("lib.clients.tmdb.tmdb.cache") as mock_cache:
        mock_cache.get.return_value = None
        with patch(
            "lib.clients.tmdb.tmdb.TMDb"
        ) as mock_tmdb_cls:
            mock_tmdb_instance = MagicMock()
            mock_tmdb_instance.language = "de-DE"
            mock_tmdb_cls.return_value = mock_tmdb_instance
            with patch(
                "lib.clients.tmdb.tmdb.tmdb_get", return_value={"logos": []}
            ):
                TmdbClient._get_cached_tmdb_item_metadata(item, "tv")
                set_call = mock_cache.set.call_args
                assert set_call[0][0] == "tmdb_ui_meta|tv|456|de-DE"
