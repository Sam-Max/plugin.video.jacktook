from lib.api.tmdbv3api.tmdb import TMDb
from lib.api.tmdbv3api.utils import get_dates

try:
    from urllib import urlencode
except ImportError:
    from urllib.parse import urlencode


class Discover(TMDb):
    _urls = {"movies": "/discover/movie", "tv": "/discover/tv"}

    def discover_movies(self, params):
        """
        Discover movies by different types of data like average rating, number of votes, genres and certifications.
        :param params: dict
        :return:
        """
        return self._request_obj(self._urls["movies"], urlencode(params), key="results")

    def discover_tv_shows(self, params):
        """
        Discover TV shows by different types of data like average rating, number of votes, genres,
        the network they aired on and air dates.
        :param params: dict
        :return:
        """
        return self._request_obj(self._urls["tv"], urlencode(params), key="results")

    def discover_tv_calendar(self, page):
        # TMDb network IDs for major streaming platforms
        # Netflix: 213, Amazon: 1024, Disney+: 2739, Hulu: 453, Apple TV+: 2552, HBO Max: 3186
        network_ids = "213,1024,2739,453,2552,3186"
        current_date, future_date = get_dates(7, reverse=False)
        params = (
            "&with_original_language=en"
            "&air_date.gte=%s"
            "&air_date.lte=%s"
            "&with_networks=%s"
            "&page=%s" % (current_date, future_date, network_ids, page)
        )
        return self._request_obj(
            self._urls["tv"],
            params=params,
        )
