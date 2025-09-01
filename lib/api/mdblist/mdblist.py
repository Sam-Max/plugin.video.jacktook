import requests
from typing import List, Dict, Any, Optional
from lib.utils.kodi.utils import get_setting


class MDblistAPIError(Exception):
    pass


class MDblistAPI:
    BASE_URL = "https://api.mdblist.com/"

    def __init__(self, provider: str = "tmdb"):
        self.api_key = str(get_setting("mdblist_api_key", ""))
        self.provider = provider
        self.session = requests.Session()

    def search_lists(self, query: str) -> List[Dict[str, Any]]:
        """
        Searches lists on MDblist by query string.
        Returns a list of dictionaries representing each matching list.
        """
        if not query:
            raise ValueError("Query string must not be empty.")
        url = f"{self.BASE_URL}lists/search"
        params = {"query": query, "apikey": self.api_key}
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise MDblistAPIError(f"Failed to search lists: {e}")

    def get_user_lists(self) -> List[Dict[str, Any]]:
        """
        Fetches user lists from MDblist API.
        Returns a list of dictionaries representing each user list.
        """
        url = f"{self.BASE_URL}lists/user"
        params = {"apikey": self.api_key}
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise MDblistAPIError(f"Failed to fetch user lists: {e}")

    def get_top_lists(self) -> List[Dict[str, Any]]:
        """
        Fetches top lists from MDblist API.
        Returns a list of dictionaries representing each top list.
        """
        url = f"{self.BASE_URL}lists/top"
        params = {"apikey": self.api_key}
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise MDblistAPIError(f"Failed to fetch top lists: {e}")

    def get_list_by_id(self, list_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetches a single list by its ID.
        Returns a dictionary representing the list, or None if not found.
        """
        if not list_id:
            raise ValueError("List ID must not be empty.")
        url = f"{self.BASE_URL}lists/{list_id}"
        params = {"apikey": self.api_key}
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            raise MDblistAPIError(f"Failed to fetch list by ID: {e}")
        except requests.RequestException as e:
            raise MDblistAPIError(f"Failed to fetch list by ID: {e}")

    def get_bulk_ratings(
        self,
        media_type: str,
        return_rating: str,
        ids: List[str],
        provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetches bulk ratings for a list of IDs from MDblist API.
        Returns a dictionary with ratings for each ID.
        """
        if not ids or not isinstance(ids, list):
            raise ValueError("IDs must be a non-empty list.")
        provider = provider or self.provider
        url = f"{self.BASE_URL}rating/{media_type}/{return_rating}"
        params = {"apikey": self.api_key}
        payload = {"ids": ids, "provider": provider}
        headers = {"Content-Type": "application/json"}
        try:
            response = self.session.post(
                url, params=params, json=payload, headers=headers
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise MDblistAPIError(f"Failed to fetch bulk ratings: {e}")

    def get_list_items(
        self,
        list_id: str,
        limit: int = 50,
        offset: int = 0,
        append_to_response: str = "genre,poster",
        filter_title: str = "",
        filter_genre: str = "",
        genre_operator: str = "or",
        released_from: str = "",
        released_to: str = "",
        sort: str = "rank",
        order: str = "asc",
        unified: bool = True,
    ) -> Dict[str, Any]:
        """
        Fetches items from a specified list with pagination and filters.
        Returns a dict with 'movies', 'shows', and pagination info.
        """
        if not list_id:
            raise ValueError("List ID must not be empty.")
        url = f"{self.BASE_URL}lists/{list_id}/items"
        params = {
            "limit": limit,
            "offset": offset,
            "append_to_response": append_to_response,
            "genre_operator": genre_operator,
            "sort": sort,
            "order": order,
            "unified": str(unified).lower(),
            "apikey": self.api_key,
        }
        if filter_title:
            params["filter_title"] = filter_title
        if filter_genre:
            params["filter_genre"] = filter_genre
        if released_from:
            params["released_from"] = released_from
        if released_to:
            params["released_to"] = released_to
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise MDblistAPIError(f"Failed to fetch list items: {e}")
