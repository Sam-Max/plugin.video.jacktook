import threading
from typing import Any

from lib.anime.display import pick_original_title, resolve_menu_record, resolve_menu_title
from lib.api.tmdbv3api.objs.anime import TmdbAnime
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
    end_of_directory,
    get_setting,
    kodilog,
    make_list_item,
    notification,
    show_keyboard,
    translation,
)

ANIMATION_GENRE_ID = 16
ANIME_KEYWORD_ID = 210024


def _has_anime_keyword(api, mode, tmdb_id):
    try:
        data = api.tmdb_keywords(mode, tmdb_id)
    except Exception as error:
        kodilog(f"[ANIME] keyword check failed for {tmdb_id}: {error}")
        return False
    if data is None:
        return False
    keywords = getattr(data, "results" if mode == "tv" else "keywords", None) or []
    return any(keyword.id == ANIME_KEYWORD_ID for keyword in keywords)


class TmdbAnimeClient(BaseTmdbClient):
    def handle_anime_search_query(self, page):
        if page == 1:
            query = show_keyboard(id=30241)
            if query:
                PickleDatabase().set_key("anime_query", query)
                return query
            return None
        return PickleDatabase().get_key("anime_query")

    @staticmethod
    def filter_anime_search_results(data, mode):
        """Keep only anime among search hits, spending requests only where needed.

        Stage 1 drops hits without the Animation genre using the search payload alone.
        Stage 2 confirms the anime keyword with one request per remaining hit; a failed
        check excludes the hit, so an unverified title never reaches the list.
        """
        candidates = [
            item
            for item in data.results
            if ANIMATION_GENRE_ID in (getattr(item, "genre_ids", None) or [])
        ]
        anime_api = TmdbAnime()
        confirmed = {}
        lock = threading.Lock()

        def confirm(indexed_item):
            index, item = indexed_item
            if _has_anime_keyword(anime_api, mode, item.id):
                with lock:
                    confirmed[index] = item

        execute_thread_pool(list(enumerate(candidates)), confirm)
        kept = [confirmed[index] for index in sorted(confirmed)]
        data.results = kept
        data.total_results = len(kept)
        return data

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
        elif category == Anime.TOP_RATED:
            set_pluging_category(translation(90042))
            return client.anime_top_rated(submode, page)
        else:
            kodilog(f"Invalid category: {category}")
            return None

    def process_anime_results(self, data, submode, page, mode, category):
        if data.total_results == 0:
            notification("No results found")
            end_of_directory(cache=False)
            return
        execute_thread_pool(data.results, TmdbAnimeClient.show_anime_results, submode)
        add_next_button("next_page_anime", page=page, mode=mode, submode=submode, category=category)
        end_of_directory()

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

    @staticmethod
    def show_anime_results(res, mode):
        tmdb_id = res.get("id", "")
        if mode == "movies":
            title = res.title
            movie_details = get_tmdb_movie_details(tmdb_id)
            imdb_id = movie_details.external_ids.get("imdb_id", "")
            tvdb_id = ""
        elif mode == "tv":
            title = res.name
            show_details = get_tmdb_show_details(tmdb_id)
            external_ids = show_details.external_ids
            imdb_id = external_ids.get("imdb_id", "")
            tvdb_id = external_ids.get("tvdb_id", "")
        else:
            kodilog(f"Invalid mode: {mode}")
            return None

        ids = {"tmdb_id": tmdb_id, "tvdb_id": tvdb_id, "imdb_id": imdb_id}
        # Previewing a TMDB-only seed can collide with a movie of the same
        # numeric id; carry the unambiguous ids plus a type hint for Simkl.
        seed = {
            "tmdb_id": tmdb_id,
            "tvdb_id": tvdb_id,
            "imdb_id": imdb_id,
            "media_type": "tv" if mode == "tv" else "movie",
        }
        list_item = make_list_item(label=title)
        set_media_infoTag(list_item, data=res, mode=mode)

        menu_title = None
        record = None
        original_title = None
        try:
            language = _coerce_title_language(get_setting("anime_title_language", 0))
            menu_title = resolve_menu_title(seed, language)
            if menu_title:
                record = resolve_menu_record(seed)
                original_title = pick_original_title(record, language)
        except Exception as error:
            kodilog(f"anime menu title resolution failed: {error}")
            menu_title, record, original_title = None, None, None

        if menu_title:
            title = menu_title
            list_item.setLabel(menu_title)
            try:
                info_tag = list_item.getVideoInfoTag()
                info_tag.setTitle(menu_title)
                if original_title:
                    info_tag.setOriginalTitle(original_title)
            except Exception as error:
                kodilog(f"anime info tag update failed: {error}")
            if record is not None:
                if record.mal_id is not None:
                    list_item.setProperty("jacktook.anime.mal_id", str(record.mal_id))
                if record.anilist_id is not None:
                    list_item.setProperty("jacktook.anime.anilist_id", str(record.anilist_id))

        TmdbAnimeClient.add_media_directory_item(list_item, mode, title, ids, anime=True)


def _coerce_title_language(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
