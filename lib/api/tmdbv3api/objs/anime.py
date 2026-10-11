from lib.api.tmdbv3api.tmdb import TMDb
from lib.api.tmdbv3api.utils import get_current_date, get_current_year, get_dates


class TmdbAnime(TMDb):
    _urls = {
        "discover_tv": "/discover/tv",
        "discover_movie": "/discover/movie",
        "search_tv": "/search/tv",
        "search_movie": "/search/movie",
        "tv_keywords": "/tv/%s/keywords",
        "movie_keywords": "/movie/%s/keywords",
    }

    def cartoons_popular(self, mode, page_no):
        return self._request_obj(
            (self._urls["discover_tv"] if mode == "tv" else self._urls["discover_movie"]),
            params=f"with_keywords=6513-cartoon&page={page_no}",
        )

    def animation_popular(self, mode, page_no):
        return self._request_obj(
            (self._urls["discover_tv"] if mode == "tv" else self._urls["discover_movie"]),
            params=f"with_keywords=297442&page={page_no}",
        )

    def anime_popular(self, mode, page_no):
        return self._request_obj(
            (self._urls["discover_tv"] if mode == "tv" else self._urls["discover_movie"]),
            params=f"with_keywords=210024&page={page_no}",
        )

    def anime_popular_recent(self, mode, page_no):
        year = get_current_year()
        if mode == "tv":
            params = f"with_keywords=210024&sort_by=first_air_date.desc&include_null_first_air_dates=false&first_air_date_year={year}&page={page_no}"
        else:
            params = f"with_keywords=210024&sort_by=primary_release_date.desc&primary_release_year={year}&page={page_no}"
        return self._request_obj(
            (self._urls["discover_tv"] if mode == "tv" else self._urls["discover_movie"]),
            params=params,
        )

    def anime_year(self, params):
        if params["mode"] == "tv":
            query = "with_keywords=210024&include_null_first_air_dates=false&first_air_date_year={}&page={}"
        else:
            query = "with_keywords=210024&primary_release_year={}&page={}"
        return self._request_obj(
            (self._urls["discover_tv"] if params["mode"] == "tv" else self._urls["discover_movie"]),
            params=query.format(params["year"], params["page"]),
        )

    def anime_genres(self, params):
        today = get_current_date()
        if params["mode"] == "tv":
            query = f"&with_keywords=210024&with_genres={{}}&include_null_first_air_dates=false&first_air_date.lte={today}&page={{}}"
        else:
            query = (
                f"&with_keywords=210024&with_genres={{}}&primary_release_date.lte={today}&page={{}}"
            )
        return self._request_obj(
            (self._urls["discover_tv"] if params["mode"] == "tv" else self._urls["discover_movie"]),
            params=query.format(params["genre_id"], params["page"]),
        )

    def anime_on_the_air(self, mode, page_no):
        current_date, future_date = get_dates(7, reverse=False)
        if mode == "tv":
            date_filter = f"air_date.gte={current_date}&air_date.lte={future_date}"
        else:
            date_filter = (
                f"primary_release_date.gte={current_date}&primary_release_date.lte={future_date}"
            )
        return self._request_obj(
            (self._urls["discover_tv"] if mode == "tv" else self._urls["discover_movie"]),
            params=f"with_keywords=210024&{date_filter}&page={page_no}",
        )

    def anime_top_rated(self, mode, page_no):
        return self._request_obj(
            (self._urls["discover_tv"] if mode == "tv" else self._urls["discover_movie"]),
            params=f"with_keywords=210024&sort_by=vote_average.desc&vote_count.gte=100&page={page_no}",
        )

    def anime_search(self, query, mode, page_no, adult=False):
        params = f"query={query}&page={page_no}"

        if adult is not None:
            params += "&include_adult={}".format("true") if adult else "false"

        return self._request_obj(
            self._urls["search_tv"] if mode == "tv" else self._urls["search_movie"],
            params=params,
            key="results",
        )

    def tmdb_keywords(self, mode, tmdb_id):
        return self._request_obj(
            (self._urls["tv_keywords"] if mode == "tv" else self._urls["movie_keywords"]) % tmdb_id,
        )
