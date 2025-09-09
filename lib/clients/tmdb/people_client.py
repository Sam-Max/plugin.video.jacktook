import json
from lib.clients.tmdb.base import BaseTmdbClient
from lib.clients.tmdb.utils.utils import add_kodi_dir_item, tmdb_get
from lib.utils.general.utils import (
    add_next_button,
    execute_thread_pool,
    set_content_type,
    set_media_infoTag,
    set_pluging_category,
)
from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    build_url,
    kodilog,
    show_keyboard,
    notification,
    translation,
)

from xbmcgui import ListItem
from xbmcplugin import endOfDirectory


class PeopleClient(BaseTmdbClient):
    def get_image_url(self, path):
        if not path:
            return ""
        base_url = "https://image.tmdb.org/t/p/w500"
        return f"{base_url}{path}"

    def search_people(self, mode, page=1):
        set_pluging_category("Search People")
        set_content_type(mode)

        query = show_keyboard(id=30241) if page == 1 else None
        if not query:
            return

        data = tmdb_get("search_people", params={"query": query, "page": page})
        if not data or getattr(data, "total_results", 0) == 0:
            notification("No results found")
            return

        execute_thread_pool(getattr(data, "results"), PeopleClient.show_people, mode)

        add_next_button(
            "handle_tmdb_query",
            query="tmdb_people",
            subquery="search_people",
            page=page + 1,
            mode=mode,
        )
        endOfDirectory(ADDON_HANDLE)

    @staticmethod
    def search_people_by_id(params):
        set_pluging_category(translation(90078))
        mode = params.get("mode", "tv")
        set_content_type(mode)

        ids = json.loads(params.get("ids", "{}"))
        tmdb_id = ids.get("tmdb_id")
        if not tmdb_id:
            notification("No TMDB ID found")
            return

        if mode == "movies":
            credits = tmdb_get("movie_credits", params=tmdb_id)
        else:
            credits = tmdb_get("tv_credits", params=tmdb_id)

        if not credits:
            notification("No credits found for this ID")
            return

        def get_media_credits(person):
            person_id = person.get("id")
            if not person_id:
                return
            PeopleClient.show_people(person, mode)

        execute_thread_pool(getattr(credits, "cast"), get_media_credits)

        endOfDirectory(ADDON_HANDLE)

    def show_popular_people(self, mode, page=1):
        kodilog(f"Fetching popular people, page {page}")
        set_pluging_category(translation(90079))
        set_content_type(mode)

        data = tmdb_get("popular_people", params=page)
        if not data or getattr(data, "total_results", 0) == 0:
            notification("No results found")
            return

        execute_thread_pool(getattr(data, "results"), PeopleClient.show_people, mode)

        add_next_button(
            "handle_tmdb_query",
            query="tmdb_people",
            subquery="popular_people",
            page=page + 1,
            mode=mode,
        )
        endOfDirectory(ADDON_HANDLE)

    def show_trending_people(self, mode, page=1):
        kodilog("Fetching trending person")
        set_pluging_category(translation(90080))
        set_content_type(mode)

        data = tmdb_get("trending_people", params=page)
        if not data or getattr(data, "total_results", 0) == 0:
            notification("No results found")
            return

        execute_thread_pool(getattr(data, "results"), PeopleClient.show_people, mode)

        add_next_button(
            "handle_tmdb_query",
            query="tmdb_people",
            subquery="latest_people",
            page=page + 1,
            mode=mode,
        )

        endOfDirectory(ADDON_HANDLE)

    @staticmethod
    def handle_tmdb_person_details(params):
        mode = params.get("mode")
        set_pluging_category("Person Details")
        set_content_type(mode)

        if mode == "movies":
            media_type = "movie"
            person_credits = tmdb_get(
                "person_movie_credits", params=params.get("person_id")
            )
            if not person_credits:
                notification("Person not found")
                return
        elif mode == "tv":
            media_type = "tv"
            person_credits = tmdb_get(
                "person_tv_credits", params=params.get("person_id")
            )
            if not person_credits:
                notification("Person not found")
                return
        else:
            notification("Invalid mode")
            return

        # Sort credits by release date (newest first)
        def get_date(c):
            return c.get("release_date") or c.get("first_air_date") or ""

        credits = sorted(
            getattr(person_credits, "cast", []), key=get_date, reverse=True
        )

        execute_thread_pool(
            credits, PeopleClient.show_credited_people, mode, media_type
        )

        endOfDirectory(ADDON_HANDLE)

    @staticmethod
    def show_credited_people(credit, mode, media_type):
        set_pluging_category("Credited People")
        title = credit.get("title") or credit.get("name") or "Unknown"

        # Extract year
        year = ""
        if credit.get("release_date"):
            year = credit["release_date"][:4]
        elif credit.get("first_air_date"):
            year = credit["first_air_date"][:4]

        # Build label with role
        label = f"{title} ({year})" if year else title
        if credit.get("character"):
            label += f" as {credit['character']}"

        tmdb_id = credit.get("id")
        details = tmdb_get(f"{media_type}_details", tmdb_id)
        imdb_id = getattr(details, "external_ids").get("imdb_id")
        tvdb_id = getattr(details, "external_ids").get("tvdb_id")

        ids = {"tmdb_id": tmdb_id, "tvdb_id": tvdb_id, "imdb_id": imdb_id}

        list_item = ListItem(label=label)
        set_media_infoTag(list_item, data=credit, mode=mode)

        if media_type == "movie":
            list_item.setProperty("IsPlayable", "true")
            add_kodi_dir_item(
                list_item=list_item,
                url=build_url(
                    "search",
                    mode="movies",
                    media_type="movies",
                    query=title,
                    ids=ids,
                ),
                is_folder=False,
            )
        else:
            add_kodi_dir_item(
                list_item=list_item,
                url=build_url(
                    "tv_seasons_details",
                    mode="tv",
                    ids=ids,
                ),
                is_folder=True,
            )

    @staticmethod
    def show_people(person, mode):
        details = tmdb_get("person_details", params=person.get("id"))
        list_item = ListItem(label=person.get("name", "Unknown"))
        set_media_infoTag(list_item, data=details, mode=mode)
        add_kodi_dir_item(
            list_item=list_item,
            url=build_url(
                "handle_tmdb_person_details", mode=mode, person_id=person.get("id")
            ),
            is_folder=True,
        )
