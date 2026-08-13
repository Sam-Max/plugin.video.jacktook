from unittest.mock import MagicMock, patch

from lib.clients.tmdb.tmdb import TmdbClient


def test_get_cached_tmdb_item_metadata_includes_language_in_cache_key():
    item = {"id": 123, "title": "Test", "media_type": "movie"}
    with patch("lib.clients.tmdb.tmdb.cache") as mock_cache:
        mock_cache.get.return_value = None
        with patch("lib.clients.tmdb.tmdb.TMDb") as mock_tmdb_cls:
            mock_tmdb_instance = MagicMock()
            mock_tmdb_instance.language = "ro-RO"
            mock_tmdb_cls.return_value = mock_tmdb_instance
            with patch("lib.clients.tmdb.tmdb.tmdb_get", return_value={"logos": []}):
                TmdbClient._get_cached_tmdb_item_metadata(item, "movies")
                get_call = mock_cache.get.call_args
                assert get_call[0][0] == "tmdb_ui_meta|movies|123|ro-RO"


def test_get_cached_tmdb_item_metadata_cache_set_uses_same_language_key():
    item = {"id": 456, "name": "Show", "media_type": "tv"}
    with patch("lib.clients.tmdb.tmdb.cache") as mock_cache:
        mock_cache.get.return_value = None
        with patch("lib.clients.tmdb.tmdb.TMDb") as mock_tmdb_cls:
            mock_tmdb_instance = MagicMock()
            mock_tmdb_instance.language = "de-DE"
            mock_tmdb_cls.return_value = mock_tmdb_instance
            with patch("lib.clients.tmdb.tmdb.tmdb_get", return_value={"logos": []}):
                TmdbClient._get_cached_tmdb_item_metadata(item, "tv")
                set_call = mock_cache.set.call_args
                assert set_call[0][0] == "tmdb_ui_meta|tv|456|de-DE"


def test_get_cached_tmdb_item_metadata_uses_list_images_without_image_request():
    item = {
        "id": 789,
        "title": "Test",
        "overview": "Overview",
        "media_type": "movie",
        "images": {"logos": [{"file_path": "/logo.png"}]},
    }
    with patch("lib.clients.tmdb.tmdb.cache") as mock_cache:
        mock_cache.get.return_value = None
        with patch("lib.clients.tmdb.tmdb.TMDb") as mock_tmdb_cls:
            mock_tmdb_instance = MagicMock()
            mock_tmdb_instance.language = "en-US"
            mock_tmdb_cls.return_value = mock_tmdb_instance
            with patch("lib.clients.tmdb.tmdb.tmdb_get") as mock_tmdb_get:
                metadata = TmdbClient._get_cached_tmdb_item_metadata(item, "movies")

    assert metadata["images"] == item["images"]
    mock_tmdb_get.assert_not_called()


def test_get_cached_tmdb_item_metadata_fetches_images_when_list_payload_omits_logos():
    item = {
        "id": 790,
        "title": "Test",
        "overview": "Overview",
        "media_type": "movie",
    }
    with patch("lib.clients.tmdb.tmdb.cache") as mock_cache:
        mock_cache.get.return_value = None
        with patch("lib.clients.tmdb.tmdb.TMDb") as mock_tmdb_cls:
            mock_tmdb_instance = MagicMock()
            mock_tmdb_instance.language = "en-US"
            mock_tmdb_cls.return_value = mock_tmdb_instance
            with patch(
                "lib.clients.tmdb.tmdb.tmdb_get", return_value={"logos": [{"file_path": "/logo.png"}]}
            ) as mock_tmdb_get:
                metadata = TmdbClient._get_cached_tmdb_item_metadata(item, "movies")

    assert metadata["images"] == {"logos": [{"file_path": "/logo.png"}]}
    mock_tmdb_get.assert_called_once_with("movie_images", {"id": 790})


def test_get_cached_tmdb_item_metadata_fetches_images_when_list_logos_are_empty():
    item = {
        "id": 792,
        "title": "Test",
        "overview": "Overview",
        "media_type": "movie",
        "images": {"logos": []},
    }
    with patch("lib.clients.tmdb.tmdb.cache") as mock_cache:
        mock_cache.get.return_value = None
        with patch("lib.clients.tmdb.tmdb.TMDb") as mock_tmdb_cls:
            mock_tmdb_instance = MagicMock()
            mock_tmdb_instance.language = "en-US"
            mock_tmdb_cls.return_value = mock_tmdb_instance
            with patch(
                "lib.clients.tmdb.tmdb.tmdb_get", return_value={"logos": [{"file_path": "/logo.png"}]}
            ) as mock_tmdb_get:
                TmdbClient._get_cached_tmdb_item_metadata(item, "movies")

    mock_tmdb_get.assert_called_once_with("movie_images", {"id": 792})


def test_get_cached_tmdb_item_metadata_falls_back_to_details_with_list_images():
    item = {
        "id": 791,
        "title": "",
        "overview": "",
        "media_type": "movie",
        "images": {"logos": [{"file_path": "/logo.png"}]},
    }
    with patch("lib.clients.tmdb.tmdb.cache") as mock_cache:
        mock_cache.get.return_value = None
        with patch("lib.clients.tmdb.tmdb.TMDb") as mock_tmdb_cls:
            mock_tmdb_instance = MagicMock()
            mock_tmdb_instance.language = "ro-RO"
            mock_tmdb_cls.return_value = mock_tmdb_instance
            with patch(
                "lib.clients.tmdb.tmdb.tmdb_get",
                return_value={"title": "English Title", "overview": "English overview"},
            ) as mock_tmdb_get:
                metadata = TmdbClient._get_cached_tmdb_item_metadata(item, "movies")

    assert metadata["title"] == "English Title"
    assert metadata["overview"] == "English overview"
    mock_tmdb_get.assert_called_once_with("movie_details", {"id": 791})
    assert mock_tmdb_instance.language == "ro-RO"
