from lib.api.tmdbv3api.tmdb import TMDb

try:
    from urllib import quote
except ImportError:
    from urllib.parse import quote


class Search(TMDb):
    _urls = {
        "companies": "/search/company",
        "collections": "/search/collection",
        "keywords": "/search/keyword",
        "movies": "/search/movie",
        "multi": "/search/multi",
        "people": "/search/person",
        "tv_shows": "/search/tv",
    }

    def companies(self, term, page=1):
        """
        Search for companies.
        :param term: str
        :param page: int
        :return:
        """
        return self._request_obj(
            self._urls["companies"],
            params=f"query={quote(term)}&page={page}",
            key="results",
        )

    def collections(self, term, page=1):
        """
        Search for collections.
        :param term: str
        :param page: int
        :return:
        """
        return self._request_obj(
            self._urls["collections"],
            params=f"query={quote(term)}&page={page}",
            key="results",
        )

    def keywords(self, term, page=1):
        """
        Search for keywords.
        :param term: str
        :param page: int
        :return:
        """
        return self._request_obj(
            self._urls["keywords"],
            params=f"query={quote(term)}&page={page}",
            key="results",
        )

    def movies(
        self,
        term,
        adult=None,
        region=None,
        year=None,
        release_year=None,
        page=1,
        append_to_response="external_ids",
    ):
        """
        Search for movies.
        :param term: str
        :param adult: bool
        :param region: str
        :param year: int
        :param release_year: int
        :param page: int
        :return:
        """
        params = f"query={quote(term)}&page={page}"
        if adult is not None:
            params += "&include_adult={}".format("true") if adult else "false"
        if region is not None:
            params += f"&region={quote(region)}"
        if year is not None:
            params += f"&year={year}"
        if release_year is not None:
            params += f"&primary_release_year={release_year}"
        params += f"&append_to_response={append_to_response}"
        return self._request_obj(self._urls["movies"], params=params, key="results")

    def multi(self, term, adult=None, region=None, page=1):
        """
        Search multiple models in a single request.
        Multi search currently supports searching for movies, tv shows and people in a single request.
        :param term: str
        :param adult: bool
        :param region: str
        :param page: int
        :return:
        """
        params = f"query={quote(term)}&page={page}"
        if adult is not None:
            params += "&include_adult={}".format("true") if adult else "false"
        if region is not None:
            params += f"&region={quote(region)}"
        return self._request_obj(self._urls["multi"], params=params, key="results")

    def people(self, term, adult=None, region=None, page=1):
        """
        Search for people.
        :param term: str
        :param adult: bool
        :param region: str
        :param page: int
        :return:
        """
        params = f"query={quote(term)}&page={page}"
        if adult is not None:
            params += "&include_adult={}".format("true") if adult else "false"
        if region is not None:
            params += f"&region={quote(region)}"
        return self._request_obj(self._urls["people"], params=params, key="results")

    def tv_shows(
        self,
        term,
        adult=None,
        release_year=None,
        page=1,
        append_to_response="external_ids",
    ):
        """
        Search for a TV show.
        :param term: str
        :param adult: bool
        :param release_year: int
        :param page: int
        :return:
        """
        params = f"query={quote(term)}&page={page}"
        if adult is not None:
            params += "&include_adult={}".format("true") if adult else "false"
        if release_year is not None:
            params += f"&first_air_date_year={release_year}"
        params += f"&append_to_response={append_to_response}"
        return self._request_obj(self._urls["tv_shows"], params=params, key="results")
