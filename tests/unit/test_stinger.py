from unittest.mock import MagicMock, patch

from lib.clients.tmdb.utils.utils import get_movie_keywords


@patch("lib.clients.tmdb.utils.utils.tmdb_get")
def test_get_movie_keywords_returns_names(mock_tmdb_get):
    mock_result = MagicMock()
    mock_result.keywords = [
        {"name": "aftercreditsstinger"},
        {"name": "superhero"},
    ]
    mock_tmdb_get.return_value = mock_result

    result = get_movie_keywords(12345)

    mock_tmdb_get.assert_called_once_with("movie_keywords", 12345)
    assert result == ["aftercreditsstinger", "superhero"]


@patch("lib.clients.tmdb.utils.utils.tmdb_get")
def test_get_movie_keywords_returns_empty_on_none(mock_tmdb_get):
    mock_tmdb_get.return_value = None

    result = get_movie_keywords(12345)

    assert result == []


@patch("lib.clients.tmdb.utils.utils.tmdb_get")
def test_get_movie_keywords_returns_empty_on_exception(mock_tmdb_get):
    mock_tmdb_get.side_effect = Exception("API error")

    result = get_movie_keywords(12345)

    assert result == []


@patch("lib.clients.tmdb.utils.utils.tmdb_get")
def test_get_movie_keywords_ignores_missing_name(mock_tmdb_get):
    mock_result = MagicMock()
    mock_result.keywords = [
        {"name": "aftercreditsstinger"},
        {"id": 999},
    ]
    mock_tmdb_get.return_value = mock_result

    result = get_movie_keywords(12345)

    assert result == ["aftercreditsstinger"]
