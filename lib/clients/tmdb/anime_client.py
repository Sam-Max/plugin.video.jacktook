from lib.clients.tmdb.base import BaseTmdbClient
from lib.clients.tmdb.utils.utils import (
    get_tmdb_movie_details,
    get_tmdb_show_details,
)

from lib.db.pickle_db import PickleDatabase
from lib.utils.general.utils import (
    Animation,
    Anime,
    Cartoons,
    add_next_button,
    execute_thread_pool,
    set_media_infoTag,
    set_pluging_category,
)

from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    kodilog,
    show_keyboard,
    notification,
    translation,
)


from xbmcgui import ListItem
from xbmcplugin import endOfDirectory


class TmdbAnimeClient(BaseTmdbClient):
    def handle_anime_search_query(self, page):
        if page == 1:
            query = show_keyboard(id=30242)
            if query:
                PickleDatabase().set_key("anime_query", query)
                return query
            return None
        return PickleDatabase().get_key("anime_query")

    def handle_anime_category_query(self, client, category, submode, page):
        if category == Anime.AIRING:
            set_pluging_category(translation(90039))
            return client.anime_on_the_air(submode, page)
        elif category == Anime.POPULAR:
            set_pluging_category(translation(90064))
            return client.anime_popular(submode, page)
        elif category == Anime.POPULAR_RECENT:
            set_pluging_category(translation(90038))
            return client.anime_popular_recent(submode, page)
        else:
            kodilog(f"Invalid category: {category}")
            return None

    def process_anime_results(self, data, submode, page, mode, category):
        if data.total_results == 0:
            notification("No results found")
            return
        execute_thread_pool(data.results, TmdbAnimeClient.show_anime_results, submode)
        add_next_button(
            "next_page_anime", page=page, mode=mode, submode=submode, category=category
        )
        endOfDirectory(ADDON_HANDLE)

    @staticmethod
    def handle_anime_years_or_genres(category, mode, page, submode):
        if category == Anime.YEARS:
            TmdbAnimeClient.show_years_items(mode, page, submode)
        elif category == Anime.GENRES:
            TmdbAnimeClient.show_genres_items(mode, page, submode)
        else:
            kodilog(f"Invalid category: {category}")
            return None

    @staticmethod
    def handle_animation_or_cartoons_query(client, category, submode, page):
        if category == Animation().POPULAR:
            return client.animation_popular(submode, page)
        elif category == Cartoons.POPULAR:
            return client.cartoons_popular(submode, page)
        else:
            kodilog(f"Invalid category: {category}")
            return None

    def show_anime_results(self, res, mode):
        tmdb_id = res.get("id", "")
        if mode == "movies":
            title = res.title
            movie_details = get_tmdb_movie_details(tmdb_id)
            imdb_id = getattr(movie_details, "external_ids").get("imdb_id", "")
            tvdb_id = ""
        elif mode == "tv":
            title = res.name
            title = res["name"]
            show_details = get_tmdb_show_details(tmdb_id)
            external_ids = getattr(show_details, "external_ids")
            imdb_id = external_ids.get("imdb_id", "")
            tvdb_id = external_ids.get("tvdb_id", "")
        else:
            kodilog(f"Invalid mode: {mode}")
            return None

        ids = {"tmdb_id": tmdb_id, "tvdb_id": tvdb_id, "imdb_id": imdb_id}
        list_item = ListItem(label=title)
        set_media_infoTag(list_item, data=res, mode=mode)
        self.add_media_directory_item(list_item, mode, title, ids)
