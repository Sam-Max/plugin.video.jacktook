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
    build_url,
    end_of_directory,
    kodilog,
    make_list_item,
    show_keyboard,
    notification,
    translation,
)


class PeopleClient(BaseTmdbClient):
    def get_image_url(self, path):
        if not path:
            return ""
        base_url = "https://image.tmdb.org/t/p/w500"
        return f"{base_url}{path}"

    def search_people(self, mode, page=1):
        set_pluging_category(translation(90081))
        set_content_type(mode)

        query = show_keyboard(id=30241) if page == 1 else None
        if not query:
            end_of_directory(cache=False)
            return

        data = tmdb_get("search_people", params={"query": query, "page": page})
        if not data or getattr(data, "total_results", 0) == 0:
            notification(translation(90389))
            end_of_directory(cache=False)
            return

        execute_thread_pool(
            getattr(data, "results"), PeopleClient.show_people_details, mode
        )

        add_next_button(
            "handle_tmdb_query",
            query="tmdb_people",
            subquery="search_people",
            page=page + 1,
            mode=mode,
        )
        end_of_directory()

    @staticmethod
    def search_people_by_id(params):
        set_pluging_category(translation(90078))
        mode = params.get("mode", "tv")
        media_type = params.get("media_type", "")
        set_content_type(mode)

        ids = json.loads(params.get("ids", "{}"))
        tmdb_id = ids.get("tmdb_id")
        if not tmdb_id:
            notification(translation(90400))
            return

        if mode == "movies" or media_type == "movie":
            credits = tmdb_get("movie_credits", params=tmdb_id)
        else:
            credits = tmdb_get("tv_credits", params=tmdb_id)

        if not credits:
            notification(translation(90418))
            return

        def get_media_credits(person):
            person_id = person.get("id")
            if not person_id:
                return
            PeopleClient.show_people_details(person, mode)

        execute_thread_pool(getattr(credits, "cast"), get_media_credits)

        end_of_directory()

    def show_popular_people(self, mode, page=1):
        set_pluging_category(translation(90079))
        set_content_type(mode)

        data = tmdb_get("popular_people", params=page)
        if not data or getattr(data, "total_results", 0) == 0:
            notification(translation(90389))
            return

        execute_thread_pool(
            getattr(data, "results"), PeopleClient.show_people_details, mode
        )

        add_next_button(
            "handle_tmdb_query",
            query="tmdb_people",
            subquery="popular_people",
            page=page + 1,
            mode=mode,
        )
        end_of_directory()

    def show_trending_people(self, mode, page=1):
        set_pluging_category(translation(90080))
        set_content_type(mode)

        data = tmdb_get("trending_people", params=page)
        if not data or getattr(data, "total_results", 0) == 0:
            notification(translation(90389))
            return

        execute_thread_pool(
            getattr(data, "results"), PeopleClient.show_people_details, mode
        )

        add_next_button(
            "handle_tmdb_query",
            query="tmdb_people",
            subquery="latest_people",
            page=page + 1,
            mode=mode,
        )

        end_of_directory()

    @staticmethod
    def show_credited_people(credit, mode, media_type):
        set_pluging_category(translation(90419))
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

        list_item = make_list_item(label=label)
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
                    "show_seasons_details",
                    mode="tv",
                    ids=ids,
                ),
                is_folder=True,
            )

    @staticmethod
    def show_people_details(person, mode):
        details = tmdb_get("person_details", params=person.get("id"))
        list_item = make_list_item(label=person.get("name", "Unknown"))
        set_media_infoTag(list_item, data=details, mode=mode)
        add_kodi_dir_item(
            list_item=list_item,
            url=build_url(
                "handle_tmdb_person_info", mode=mode, person_id=person.get("id")
            ),
            is_folder=False,
        )

    @staticmethod
    def handle_tmdb_person_info(params):
        from lib.gui.actor_info_window import ActorInfoWindow
        from lib.utils.kodi.utils import ADDON_PATH

        mode = params.get("mode")
        person_id = params.get("person_id")
        window = ActorInfoWindow(
            "actor_info.xml",
            ADDON_PATH,
            person_id=person_id,
        )
        window.doModal()
        del window

    @staticmethod
    def handle_tmdb_person_details(params):
        mode = params.get("mode")
        set_pluging_category(translation(90420))
        set_content_type(mode)

        if mode == "movies":
            media_type = "movie"
            person_credits = tmdb_get(
                "person_movie_credits", params=params.get("person_id")
            )
            if not person_credits:
                notification(translation(90421))
                return
        elif mode == "tv":
            media_type = "tv"
            person_credits = tmdb_get(
                "person_tv_credits", params=params.get("person_id")
            )
            if not person_credits:
                notification(translation(90421))
                return
        else:
            notification(translation(90390))
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

        end_of_directory()
