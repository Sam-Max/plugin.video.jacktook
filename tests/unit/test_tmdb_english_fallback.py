import pytest
from unittest.mock import patch, MagicMock
from datetime import timedelta


class TestTmdbEnglishFallback:
    @patch("lib.clients.tmdb.tmdb.TMDb")
    @patch("lib.clients.tmdb.tmdb.cache")
    @patch("lib.clients.tmdb.tmdb.tmdb_get")
    def test_no_fallback_when_localized_data_complete(self, mock_tmdb_get, mock_cache, MockTMDb):
        mock_tmdb = MagicMock()
        mock_tmdb.language = "ro-RO"
        MockTMDb.return_value = mock_tmdb

        mock_cache.get.return_value = None

        from lib.clients.tmdb.tmdb import TmdbClient

        item = {
            "id": 123,
            "title": "Titlu Românesc",
            "overview": "Descriere în română",
            "media_type": "movie",
        }

        metadata = TmdbClient._get_cached_tmdb_item_metadata(item, "movies")

        assert metadata["title"] == "Titlu Românesc"
        assert metadata["overview"] == "Descriere în română"
        # Should NOT call details endpoint for fallback
        detail_calls = [c for c in mock_tmdb_get.call_args_list if c[0][0] in ("movie_details", "tv_details")]
        assert len(detail_calls) == 0

    @patch("lib.clients.tmdb.tmdb.TMDb")
    @patch("lib.clients.tmdb.tmdb.cache")
    @patch("lib.clients.tmdb.tmdb.tmdb_get")
    def test_fallback_to_english_when_title_missing(self, mock_tmdb_get, mock_cache, MockTMDb):
        mock_tmdb = MagicMock()
        mock_tmdb.language = "ro-RO"
        MockTMDb.return_value = mock_tmdb

        mock_cache.get.return_value = None

        def tmdb_get_side_effect(path, params):
            if path == "movie_images":
                return None
            if path == "movie_details":
                return {
                    "id": 123,
                    "title": "English Title",
                    "overview": "English overview",
                }
            return None

        mock_tmdb_get.side_effect = tmdb_get_side_effect

        from lib.clients.tmdb.tmdb import TmdbClient

        item = {
            "id": 123,
            "title": "",
            "name": "",
            "overview": "",
            "media_type": "movie",
        }

        metadata = TmdbClient._get_cached_tmdb_item_metadata(item, "movies")

        assert metadata["title"] == "English Title"
        assert metadata["overview"] == "English overview"
        # Should restore original language
        assert mock_tmdb.language == "ro-RO"

    @patch("lib.clients.tmdb.tmdb.TMDb")
    @patch("lib.clients.tmdb.tmdb.cache")
    @patch("lib.clients.tmdb.tmdb.tmdb_get")
    def test_fallback_to_english_when_overview_missing(self, mock_tmdb_get, mock_cache, MockTMDb):
        mock_tmdb = MagicMock()
        mock_tmdb.language = "ro-RO"
        MockTMDb.return_value = mock_tmdb

        mock_cache.get.return_value = None

        def tmdb_get_side_effect(path, params):
            if path == "movie_images":
                return None
            if path == "movie_details":
                return {
                    "id": 123,
                    "title": "Titlu Românesc",
                    "overview": "English overview",
                }
            return None

        mock_tmdb_get.side_effect = tmdb_get_side_effect

        from lib.clients.tmdb.tmdb import TmdbClient

        item = {
            "id": 123,
            "title": "Titlu Românesc",
            "overview": "",
            "media_type": "movie",
        }

        metadata = TmdbClient._get_cached_tmdb_item_metadata(item, "movies")

        assert metadata["title"] == "Titlu Românesc"
        assert metadata["overview"] == "English overview"

    @patch("lib.clients.tmdb.tmdb.TMDb")
    @patch("lib.clients.tmdb.tmdb.cache")
    @patch("lib.clients.tmdb.tmdb.tmdb_get")
    def test_fallback_for_tv_shows(self, mock_tmdb_get, mock_cache, MockTMDb):
        mock_tmdb = MagicMock()
        mock_tmdb.language = "ro-RO"
        MockTMDb.return_value = mock_tmdb

        mock_cache.get.return_value = None

        def tmdb_get_side_effect(path, params):
            if path == "tv_images":
                return None
            if path == "tv_details":
                return {
                    "id": 456,
                    "name": "English Show Name",
                    "overview": "English show overview",
                }
            return None

        mock_tmdb_get.side_effect = tmdb_get_side_effect

        from lib.clients.tmdb.tmdb import TmdbClient

        item = {
            "id": 456,
            "name": "",
            "overview": "",
            "media_type": "tv",
        }

        metadata = TmdbClient._get_cached_tmdb_item_metadata(item, "tv")

        assert metadata["name"] == "English Show Name"
        assert metadata["overview"] == "English show overview"
        assert mock_tmdb.language == "ro-RO"

    @patch("lib.clients.tmdb.tmdb.TMDb")
    @patch("lib.clients.tmdb.tmdb.cache")
    @patch("lib.clients.tmdb.tmdb.tmdb_get")
    def test_uses_cached_metadata_when_available(self, mock_tmdb_get, mock_cache, MockTMDb):
        mock_tmdb = MagicMock()
        mock_tmdb.language = "ro-RO"
        MockTMDb.return_value = mock_tmdb

        mock_cache.get.return_value = {
            "title": "Cached Title",
            "overview": "Cached overview",
            "images": {"posters": []},
        }

        from lib.clients.tmdb.tmdb import TmdbClient

        item = {
            "id": 123,
            "title": "",
            "overview": "",
            "media_type": "movie",
        }

        metadata = TmdbClient._get_cached_tmdb_item_metadata(item, "movies")

        assert metadata["title"] == "Cached Title"
        assert metadata["overview"] == "Cached overview"
        # Should NOT make any API calls when cache hit
        assert mock_tmdb_get.call_count == 0
