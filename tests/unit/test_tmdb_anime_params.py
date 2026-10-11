import datetime
from urllib.parse import parse_qs

import pytest

from lib.api.tmdbv3api.objs.anime import TmdbAnime

ANIME_KEYWORD = "210024"


@pytest.fixture
def requests_log(monkeypatch):
    """Record (action, params) of every discover request instead of calling TMDB."""
    calls = []

    def fake_request_obj(self, action, params="", **kwargs):
        calls.append((action, parse_qs(params)))
        return None

    monkeypatch.setattr(TmdbAnime, "_request_obj", fake_request_obj)
    return calls


def _current_year():
    return str(datetime.date.today().year)


def test_popular_recent_tv_uses_current_year_and_tv_filters(requests_log):
    TmdbAnime().anime_popular_recent("tv", 1)

    action, params = requests_log[-1]
    assert action == "/discover/tv"
    assert params["first_air_date_year"] == [_current_year()]
    assert params["sort_by"] == ["first_air_date.desc"]
    assert params["with_keywords"] == [ANIME_KEYWORD]


def test_popular_recent_movies_uses_primary_release_filters(requests_log):
    TmdbAnime().anime_popular_recent("movies", 1)

    action, params = requests_log[-1]
    assert action == "/discover/movie"
    assert params["primary_release_year"] == [_current_year()]
    assert params["sort_by"] == ["primary_release_date.desc"]
    assert params["with_keywords"] == [ANIME_KEYWORD]
    assert "first_air_date_year" not in params
    assert "first_air_date.desc" not in params.get("sort_by", [])


def test_on_the_air_tv_keeps_air_date_window(requests_log):
    TmdbAnime().anime_on_the_air("tv", 1)

    action, params = requests_log[-1]
    assert action == "/discover/tv"
    assert "air_date.gte" in params
    assert "air_date.lte" in params


def test_on_the_air_movies_uses_primary_release_window_not_tv_air_dates(requests_log):
    TmdbAnime().anime_on_the_air("movies", 1)

    action, params = requests_log[-1]
    assert action == "/discover/movie"
    assert "primary_release_date.gte" in params
    assert "primary_release_date.lte" in params
    assert "air_date.gte" not in params
    assert "air_date.lte" not in params


def test_genres_movies_drops_tv_only_filters(requests_log):
    TmdbAnime().anime_genres({"mode": "movies", "genre_id": 16, "page": 1})

    action, params = requests_log[-1]
    assert action == "/discover/movie"
    assert params["with_genres"] == ["16"]
    assert "first_air_date.lte" not in params
    assert "include_null_first_air_dates" not in params
    assert "primary_release_date.lte" in params


def test_genres_tv_keeps_first_air_date_filters(requests_log):
    TmdbAnime().anime_genres({"mode": "tv", "genre_id": 16, "page": 1})

    action, params = requests_log[-1]
    assert action == "/discover/tv"
    assert "first_air_date.lte" in params
    assert params["include_null_first_air_dates"] == ["false"]


def test_year_movies_drops_include_null_first_air_dates(requests_log):
    TmdbAnime().anime_year({"mode": "movies", "year": 2020, "page": 1})

    action, params = requests_log[-1]
    assert action == "/discover/movie"
    assert params["primary_release_year"] == ["2020"]
    assert "include_null_first_air_dates" not in params


def test_year_tv_keeps_first_air_date_year(requests_log):
    TmdbAnime().anime_year({"mode": "tv", "year": 2020, "page": 1})

    action, params = requests_log[-1]
    assert action == "/discover/tv"
    assert params["first_air_date_year"] == ["2020"]
    assert params["include_null_first_air_dates"] == ["false"]


@pytest.mark.parametrize("mode", ["tv", "movies"])
def test_top_rated_and_popular_keep_anime_keyword_and_sort(requests_log, mode):
    TmdbAnime().anime_top_rated(mode, 1)
    TmdbAnime().anime_popular(mode, 1)

    top_rated, popular = requests_log[-2], requests_log[-1]
    assert top_rated[1]["with_keywords"] == [ANIME_KEYWORD]
    assert top_rated[1]["sort_by"] == ["vote_average.desc"]
    assert popular[1]["with_keywords"] == [ANIME_KEYWORD]
