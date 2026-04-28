import pytest
from unittest.mock import patch, MagicMock


class TestEnsureTmdbInit:
    @patch("lib.utils.tmdb_init.get_setting")
    @patch("lib.utils.tmdb_init.TMDb")
    def test_initializes_api_key_and_language(self, MockTMDb, mock_get_setting):
        mock_tmdb = MagicMock()
        MockTMDb.return_value = mock_tmdb
        mock_get_setting.side_effect = lambda key, default=None: {
            "tmdb_api_key": "test-key",
            "language": 20,
        }.get(key, default)

        from lib.utils.tmdb_init import ensure_tmdb_init

        ensure_tmdb_init()

        assert mock_tmdb.api_key == "test-key"
        assert mock_tmdb.language == "es-ES"

    @patch("lib.utils.tmdb_init.get_setting")
    @patch("lib.utils.tmdb_init.TMDb")
    def test_updates_language_on_subsequent_calls(self, MockTMDb, mock_get_setting):
        mock_tmdb = MagicMock()
        MockTMDb.return_value = mock_tmdb

        # First call: English
        mock_get_setting.side_effect = lambda key, default=None: {
            "tmdb_api_key": "test-key",
            "language": 18,
        }.get(key, default)

        from lib.utils.tmdb_init import ensure_tmdb_init

        ensure_tmdb_init()
        assert mock_tmdb.language == "en-US"

        # Second call: Romanian (index 50 in LANGUAGES)
        mock_get_setting.side_effect = lambda key, default=None: {
            "tmdb_api_key": "test-key",
            "language": 50,
        }.get(key, default)

        ensure_tmdb_init()
        assert mock_tmdb.language == "ro-RO"

    @patch("lib.utils.tmdb_init.get_setting")
    @patch("lib.utils.tmdb_init.TMDb")
    def test_invalid_language_index_fallbacks_to_en_us(self, MockTMDb, mock_get_setting):
        mock_tmdb = MagicMock()
        MockTMDb.return_value = mock_tmdb
        mock_get_setting.side_effect = lambda key, default=None: {
            "tmdb_api_key": "test-key",
            "language": 999,
        }.get(key, default)

        from lib.utils.tmdb_init import ensure_tmdb_init

        ensure_tmdb_init()

        assert mock_tmdb.language == "en-US"
