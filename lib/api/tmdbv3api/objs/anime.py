from lib.api.tmdbv3api.tmdb import TMDb
from lib.api.tmdbv3api.utils import get_dates, years_tvshows


class Anime(TMDb):
    _urls = {
        "discover_tv": "/discover/tv",
        "discover_movie": "/discover/movie",
        "search_tv": "/search/tv",
        "search_movie": "/search/movie",
        "tv_keywords": "/tv/%s/keywords",
        "movie_keywords": "/movie/%s/keywords",
    }

    def anime_popular(self, mode, page_no):
        return self._request_obj(
            (
                self._urls["discover_tv"]
                if mode == "tv"
                else self._urls["discover_movie"]
            ),
            params="with_keywords=210024&page=%s" % page_no,
        )

    def anime_popular_recent(self, mode, page_no):
        return self._request_obj(
            (
                self._urls["discover_tv"]
                if mode == "tv"
                else self._urls["discover_movie"]
            ),
            params=(
                "with_keywords=210024&sort_by=first_air_date.desc&include_null_first_air_dates=false&first_air_date_year=%s&page=%s"
                % (years_tvshows[0]["id"], page_no)
            ),
        )

    def anime_on_the_air(self, mode, page_no):
        current_date, future_date = get_dates(7, reverse=False)
        return self._request_obj(
            (
                self._urls["discover_tv"]
                if mode == "tv"
                else self._urls["discover_movie"]
            ),
            params="with_keywords=210024&air_date.gte=%s&air_date.lte=%s&page=%s"
            % (current_date, future_date, page_no),
        )

    def anime_search(self, query, mode, page_no, adult=False):
        params = "query=%s&page=%s" % (query, page_no)

        if adult is not None:
            params += "&include_adult=%s" % "true" if adult else "false"

        return self._request_obj(
            self._urls["search_tv"] if mode == "tv" else self._urls["search_movie"],
            params=params,
            key="results",
        )

    def tmdb_keywords(self, mode, tmdb_id):
        return self._request_obj(
            (
                self._urls["tv_keywords"]
                if mode == "tv"
                else self._urls["movie_keywords"] 
            ) % tmdb_id,
        )