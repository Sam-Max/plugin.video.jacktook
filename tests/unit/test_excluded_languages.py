from unittest.mock import MagicMock, patch

from lib.clients.tmdb.utils.utils import (
    filter_excluded_languages,
    get_excluded_languages,
)


class TestGetExcludedLanguages:
    def test_returns_empty_list_by_default(self):
        with patch("lib.clients.tmdb.utils.utils.get_setting", return_value="[]"):
            assert get_excluded_languages() == []

    def test_returns_parsed_json(self):
        with patch(
            "lib.clients.tmdb.utils.utils.get_setting", return_value='["ja", "ko"]'
        ):
            assert get_excluded_languages() == ["ja", "ko"]

    def test_returns_empty_on_invalid_json(self):
        with patch("lib.clients.tmdb.utils.utils.get_setting", return_value="not-json"):
            assert get_excluded_languages() == []


class TestFilterExcludedLanguages:
    def test_returns_all_when_none_excluded(self):
        results = [
            MagicMock(original_language="en"),
            MagicMock(original_language="ja"),
        ]
        with patch(
            "lib.clients.tmdb.utils.utils.get_excluded_languages", return_value=[]
        ):
            filtered = filter_excluded_languages(results)
        assert len(filtered) == 2

    def test_filters_excluded_languages(self):
        results = [
            MagicMock(original_language="en"),
            MagicMock(original_language="ja"),
            MagicMock(original_language="ko"),
        ]
        with patch(
            "lib.clients.tmdb.utils.utils.get_excluded_languages",
            return_value=["ja", "ko"],
        ):
            filtered = filter_excluded_languages(results)
        assert len(filtered) == 1
        assert filtered[0].original_language == "en"

    def test_allows_force_allow_lang(self):
        results = [
            MagicMock(original_language="en"),
            MagicMock(original_language="ja"),
        ]
        with patch(
            "lib.clients.tmdb.utils.utils.get_excluded_languages",
            return_value=["ja"],
        ):
            filtered = filter_excluded_languages(results, force_allow_lang="ja")
        assert len(filtered) == 2
        assert filtered[0].original_language == "en"
        assert filtered[1].original_language == "ja"

    def test_handles_dict_results(self):
        results = [
            {"original_language": "en"},
            {"original_language": "ja"},
        ]
        with patch(
            "lib.clients.tmdb.utils.utils.get_excluded_languages",
            return_value=["ja"],
        ):
            filtered = filter_excluded_languages(results)
        assert len(filtered) == 1
        assert filtered[0]["original_language"] == "en"

    def test_handles_none_original_language(self):
        results = [
            MagicMock(original_language="en"),
            MagicMock(original_language=None),
        ]
        with patch(
            "lib.clients.tmdb.utils.utils.get_excluded_languages",
            return_value=["ja"],
        ):
            filtered = filter_excluded_languages(results)
        assert len(filtered) == 2
