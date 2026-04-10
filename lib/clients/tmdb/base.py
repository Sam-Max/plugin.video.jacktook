from datetime import datetime

from lib.api.tmdbv3api.as_obj import AsObj
from lib.utils.general.utils import set_pluging_category
from lib.utils.kodi.utils import (
    add_directory_items_batch,
    apply_section_view,
    build_url,
    end_of_directory,
    make_list_item,
    notification,
    translation,
)
from lib.clients.tmdb.utils.utils import (
    add_kodi_dir_item,
    add_tmdb_movie_context_menu,
    add_tmdb_show_context_menu,
    tmdb_get,
)
from lib.api.trakt.trakt_utils import (
    add_trakt_collection_context_menu,
    add_trakt_custom_list_context_menu,
    add_trakt_favorites_context_menu,
    add_trakt_watchlist_context_menu,
    add_trakt_watched_context_menu,
    is_trakt_auth,
)


class BaseTmdbClient:
    @staticmethod
    def add_media_directory_item(list_item, mode, title, ids, media_type="", batch=False):
        if mode == "movies" or (mode == "multi" and media_type == "movie"):
            context_menu = add_tmdb_movie_context_menu(
                mode, media_type, title=title, ids=ids
            )
            if is_trakt_auth():
                context_menu += (
                    add_trakt_watchlist_context_menu("movies", ids)
                    + add_trakt_watched_context_menu("movies", ids=ids)
                    + add_trakt_collection_context_menu("movies", ids)
                    + add_trakt_favorites_context_menu("movies", ids)
                    + add_trakt_custom_list_context_menu("movies", ids)
                )
            list_item.addContextMenuItems(context_menu)
            list_item.setProperty("IsPlayable", "true")
            is_folder = False
        elif mode == "tv" or (mode == "multi" and media_type == "tv"):
            context_menu = add_tmdb_show_context_menu(mode, ids=ids, title=title)
            if is_trakt_auth():
                context_menu += (
                    add_trakt_watchlist_context_menu("shows", ids)
                    + add_trakt_watched_context_menu("shows", ids=ids)
                    + add_trakt_collection_context_menu("shows", ids)
                    + add_trakt_favorites_context_menu("shows", ids)
                    + add_trakt_custom_list_context_menu("shows", ids)
                )
            list_item.addContextMenuItems(context_menu)
            is_folder = True
        else:
            is_folder = True

        url = build_url(
            "show_tmdb_item",
            mode=mode,
            submode="",
            id=ids.get("tmdb_id"),
            title=title,
            media_type=media_type,
        )
        if batch:
            return (url, list_item, is_folder)
        add_kodi_dir_item(
            list_item=list_item,
            url=url,
            is_folder=is_folder,
        )

    @staticmethod
    def show_years_items(mode, page, submode=None):
        set_pluging_category(translation(90027))
        directory_items = []
        current_year = datetime.now().year
        for year in range(current_year, 1899, -1):
            list_item = make_list_item(label=str(year))
            item = add_kodi_dir_item(
                list_item=list_item,
                url=build_url(
                    "search_tmdb_year",
                    mode=mode,
                    submode=submode,
                    year=year,
                    page=page,
                ),
                is_folder=True,
                icon_path="status.png",
                batch=True,
            )
            directory_items.append(item)
        add_directory_items_batch(directory_items)
        end_of_directory()
        if mode == "tv" or (mode == "anime" and submode == "tv"):
            apply_section_view("view.tvshows", content_type="tvshows", fallback="poster")
        else:
            apply_section_view("view.movies", content_type="movies", fallback="poster")

    @staticmethod
    def show_genres_items(mode, page, submode=None):
        set_pluging_category(translation(90025))
        path = (
            "show_genres"
            if mode == "tv" or (mode == "anime" and submode == "tv")
            else "movie_genres"
        )
        genres = tmdb_get(path=path)
        if genres is None or len(genres) == 0:
            notification("No genres found")
            end_of_directory()
            return

        directory_items = []
        for genre in genres:
            if isinstance(genre, AsObj):
                if genre.get("name") == "TV Movie":
                    continue
                list_item = make_list_item(label=genre["name"])
                item = add_kodi_dir_item(
                    list_item=list_item,
                    url=build_url(
                        "search_tmdb_genres",
                        mode=mode,
                        submode=submode,
                        genre_id=genre["id"],
                        page=page,
                    ),
                    is_folder=True,
                    icon_path=None,
                    batch=True,
                )
                directory_items.append(item)
        add_directory_items_batch(directory_items)
        end_of_directory()
        if mode == "tv" or (mode == "anime" and submode == "tv"):
            apply_section_view("view.tvshows", content_type="tvshows", fallback="poster")
        else:
            apply_section_view("view.movies", content_type="movies", fallback="poster")
