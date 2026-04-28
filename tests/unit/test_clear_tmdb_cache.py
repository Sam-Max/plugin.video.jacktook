from unittest.mock import MagicMock, patch

from lib.utils.general.utils import clear_tmdb_cache


def test_clear_tmdb_cache_deletes_tmdb_ui_meta_entries():
    with patch("lib.utils.general.utils.cache") as mock_cache:
        with patch("lib.utils.general.utils.notification"):
            with patch("lib.utils.general.utils.translation", return_value=""):
                with patch(
                    "lib.utils.general.utils.TMDb"
                ) as mock_tmdb_cls:
                    mock_tmdb_instance = MagicMock()
                    mock_tmdb_cls.return_value = mock_tmdb_instance
                    clear_tmdb_cache()
                    # Verify tmdb_ui_meta prefix is deleted
                    delete_like_calls = [
                        call for call in mock_cache.method_calls
                        if call[0] == "delete_like" and "tmdb_ui_meta" in call[1][0]
                    ]
                    assert len(delete_like_calls) == 1
                    assert delete_like_calls[0][1][0] == "tmdb_ui_meta|%"


def test_clear_tmdb_cache_calls_tmdb_cache_clear():
    with patch("lib.utils.general.utils.cache"):
        with patch("lib.utils.general.utils.notification"):
            with patch("lib.utils.general.utils.translation", return_value=""):
                with patch(
                    "lib.utils.general.utils.TMDb"
                ) as mock_tmdb_cls:
                    mock_tmdb_instance = MagicMock()
                    mock_tmdb_cls.return_value = mock_tmdb_instance
                    clear_tmdb_cache()
                    mock_tmdb_instance.cache_clear.assert_called_once()


def test_clear_tmdb_cache_still_deletes_other_prefixes():
    with patch("lib.utils.general.utils.cache") as mock_cache:
        with patch("lib.utils.general.utils.notification"):
            with patch("lib.utils.general.utils.translation", return_value=""):
                with patch("lib.utils.general.utils.TMDb"):
                    clear_tmdb_cache()
                    # Verify some legacy prefixes are still deleted
                    delete_like_calls = [call[1][0] for call in mock_cache.method_calls if call[0] == "delete_like"]
                    assert "search_%|%" in delete_like_calls
                    assert "movie_%|%" in delete_like_calls
