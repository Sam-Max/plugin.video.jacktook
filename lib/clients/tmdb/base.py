from datetime import datetime

from lib.api.tmdbv3api.as_obj import AsObj
from lib.api.trakt.trakt_utils import (
    add_trakt_watched_context_menu,
    add_trakt_watchlist_context_menu,
    is_trakt_auth,
)
from lib.utils.general.utils import set_pluging_category
from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    build_url,
    notification,
    set_view,
    translation,
)
from lib.clients.tmdb.utils.utils import (
    add_kodi_dir_item,
    add_tmdb_movie_context_menu,
    add_tmdb_show_context_menu,
    tmdb_get,
)

from xbmcgui import ListItem
from xbmcplugin import endOfDirectory


class BaseTmdbClient:
    @staticmethod
    def add_media_directory_item(
        list_item, mode, title, ids, seasons_number=1, media_type=None
    ):
        if mode == "movies":
            context_menu = add_tmdb_movie_context_menu(mode, title=title, ids=ids)
            if is_trakt_auth():
                context_menu += add_trakt_watchlist_context_menu(
                    "movies", ids
                ) + add_trakt_watched_context_menu("movies", ids=ids)
            list_item.addContextMenuItems(context_menu)
            add_kodi_dir_item(
                list_item=list_item,
                url=build_url(
                    "search",
                    mode=mode,
                    query=title,
                    ids=ids,
                ),
                is_folder=False,
                set_playable=True,
            )
        else:
            context_menu = add_tmdb_show_context_menu(mode, ids=ids)
            if is_trakt_auth():
                context_menu += add_trakt_watchlist_context_menu(
                    "shows", ids
                ) + add_trakt_watched_context_menu("shows", ids=ids)
            list_item.addContextMenuItems(context_menu)
            if seasons_number == 1:
                add_kodi_dir_item(
                    list_item=list_item,
                    url=build_url(
                        "tv_episodes_details",
                        tv_name=title,
                        ids=ids,
                        mode=mode,
                        media_type=media_type,
                        season=seasons_number,
                    ),
                    is_folder=True,
                )
            else:
                add_kodi_dir_item(
                    list_item=list_item,
                    url=build_url(
                        "tv_seasons_details",
                        ids=ids,
                        mode=mode,
                        media_type=media_type,
                    ),
                    is_folder=True,
                )

    @staticmethod
    def show_years_items(mode, page, submode=None):
        set_pluging_category(translation(90027))
        current_year = datetime.now().year
        for year in range(current_year, 1899, -1):
            list_item = ListItem(label=str(year))
            add_kodi_dir_item(
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
            )
        endOfDirectory(ADDON_HANDLE)
        set_view("widelist")

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
            endOfDirectory(ADDON_HANDLE)
            return

        for genre in genres:
            if isinstance(genre, AsObj):
                if genre.get("name") == "TV Movie":
                    continue
                list_item = ListItem(label=genre["name"])
                add_kodi_dir_item(
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
                )
        endOfDirectory(ADDON_HANDLE)
        set_view("widelist")
