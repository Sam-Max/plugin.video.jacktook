from lib.clients.tmdb.utils.collections_utils import (
    POPULAR_COLLECTIONS,
    TOP_RATED_COLLECTIONS,
)
from lib.clients.tmdb.tmdb import BaseTmdbClient
from lib.db.pickle_db import PickleDatabase
from lib.utils.general.utils import (
    add_next_button,
    execute_thread_pool,
    set_media_infoTag,
    set_pluging_category,
)

from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    build_url,
    set_view,
    show_keyboard,
    notification,
    translation,
)
from lib.clients.tmdb.utils.utils import (
    tmdb_get,
    add_kodi_dir_item,
    get_tmdb_movie_details,
)

from xbmcgui import ListItem
from xbmcplugin import endOfDirectory


class TmdbCollections(BaseTmdbClient):
    PAGE_SIZE = 10

    @staticmethod
    def add_collection_details(params):
        collection = tmdb_get("collection_details", params.get("collection_id"))
        if not collection:
            notification("Collection details not found.")
            endOfDirectory(ADDON_HANDLE)
            return

        parts = collection.get("parts", [])
        for movie in parts:
            movie_item = ListItem(label=movie.get("title", "Untitled"))
            movie_item.setProperty("IsPlayable", "true")
            set_media_infoTag(movie_item, data=movie, mode="movie")

            tmdb_id = movie.get("id")
            imdb_id = ""
            details = get_tmdb_movie_details(tmdb_id)
            if details:
                imdb_id = getattr(details, "external_ids").get("imdb_id", "")

            add_kodi_dir_item(
                list_item=movie_item,
                url=build_url(
                    "search",
                    mode="movies",
                    media_type="movies",
                    query=movie.get("title", "Untitled"),
                    ids={"tmdb_id": tmdb_id, "imdb_id": imdb_id},
                ),
                is_folder=False,
            )

        endOfDirectory(ADDON_HANDLE)
        set_view("widelist")

    @staticmethod
    def _add_collection_item(collection):
        collection_id = collection.get("id")
        images_data = tmdb_get("collection_images", collection_id)
        if images_data:
            posters = images_data.get("posters") or []
            if posters:
                file_path = posters[0].get("file_path")
                collection["poster_path"] = file_path

        list_item = ListItem(label=collection.get("name"))
        set_media_infoTag(list_item, data=collection, mode="movies")
        add_kodi_dir_item(
            list_item=list_item,
            url=build_url("handle_collection_details", collection_id=collection_id),
            is_folder=True,
        )

    @staticmethod
    def fetch_and_add_collection(collection_data):
        collection_id = collection_data["id"]
        collection_details = tmdb_get("collection_details", collection_id)
        if collection_details:
            TmdbCollections._add_collection_item(collection_details)

    @staticmethod
    def get_popular_collections(mode, page):
        set_pluging_category(translation(90064))

        start_index = (page - 1) * TmdbCollections.PAGE_SIZE
        end_index = start_index + TmdbCollections.PAGE_SIZE

        current_page_collections = POPULAR_COLLECTIONS[start_index:end_index]

        if not current_page_collections:
            notification("No more popular collections to display.")
            endOfDirectory(ADDON_HANDLE)
            return

        execute_thread_pool(
            current_page_collections, TmdbCollections.fetch_and_add_collection
        )

        # Add "Next" button
        if end_index < len(POPULAR_COLLECTIONS):
            add_next_button(
                "handle_collection_query", submode="popular", page=page + 1, mode=mode
            )

        endOfDirectory(ADDON_HANDLE)
        set_view("widelist")

    @staticmethod
    def get_top_rated_collections(mode, page):
        set_pluging_category(translation(90042))

        start_index = (page - 1) * TmdbCollections.PAGE_SIZE
        end_index = start_index + TmdbCollections.PAGE_SIZE

        current_page_collections = TOP_RATED_COLLECTIONS[start_index:end_index]

        if not current_page_collections:
            notification("No more collections to display.")
            endOfDirectory(ADDON_HANDLE)
            return

        execute_thread_pool(
            current_page_collections, TmdbCollections.fetch_and_add_collection
        )

        # Add "Next" button
        if end_index < len(TOP_RATED_COLLECTIONS):
            add_next_button(
                "handle_collection_query", submode="top_rated", page=page + 1, mode=mode
            )

        endOfDirectory(ADDON_HANDLE)
        set_view("widelist")

    @staticmethod
    def search_collections(mode, page):
        query = (
            show_keyboard(id=90068)
            if page == 1
            else PickleDatabase().get_key("collection_search_query")
        )
        if not query:
            return

        if page == 1:
             PickleDatabase().set_key("collection_search_query", query)

        results = tmdb_get("search_collections", params={"query": query, "page": page})
        if not results or getattr(results, "total_results", 0) == 0:
            notification("No results found for your search.")
            endOfDirectory(ADDON_HANDLE)
            return

        execute_thread_pool(
            getattr(results, "results"), TmdbCollections._add_collection_item
        )

        add_next_button(
            "handle_collection_query",
            submode="search",
            query=query,
            page=page + 1,
            mode=mode,
        )
        endOfDirectory(ADDON_HANDLE)
        set_view("widelist")

    @staticmethod
    def _extract_collection_id(movie, collection_ids_set):
        from lib.clients.tmdb.utils.utils import get_tmdb_movie_details

        """
        Helper function to extract collection ID from movie details.
        Designed to be used with execute_thread_pool.
        """
        movie_details = get_tmdb_movie_details(getattr(movie, "id"))
        if movie_details and getattr(movie_details, "belongs_to_collection"):
            collection_ids_set.add(movie_details.get("belongs_to_collection").get("id"))
