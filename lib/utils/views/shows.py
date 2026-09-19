import json
from urllib.parse import quote

from lib.anime.display import apply_anime_extras, resolve_menu_extras
from lib.api.trakt.trakt_utils import add_trakt_watched_context_menu, is_trakt_auth
from lib.clients.tmdb.utils.utils import (
    add_tmdb_episode_context_menu,
    add_tmdb_show_context_menu,
    tmdb_get,
)
from lib.utils.general.utils import (
    execute_thread_pool_collection,
    get_fanart_details,
    set_content_type,
    set_media_infoTag,
    truthy_param,
)
from lib.utils.kodi.utils import (
    add_directory_items_batch,
    apply_section_view,
    build_url,
    end_of_directory,
    get_setting,
    kodilog,
    make_list_item,
)
from lib.utils.nuvio_context import add_nuvio_history_context_menu
from lib.utils.simkl_context import add_simkl_history_context_menu


def _anime_extras(ids, mode, media_type):
    """Resolve anime cast/staff/studio extras once for the opened title.

    The seed mirrors the one the anime menus already use so this lookup hits the
    same cached identity record. Never raises.
    """
    try:
        seed = dict(ids) if isinstance(ids, dict) else {}
        hint = media_type if media_type in ("tv", "movie") else None
        if hint is None:
            hint = "movie" if mode in ("movie", "movies") else "tv"
        seed["media_type"] = hint
        return resolve_menu_extras(seed)
    except Exception as error:
        kodilog(f"[ANIME] extras resolution failed: {error}")
        return None


def _apply_anime_extras(results, extras):
    """Apply the pre-resolved anime extras to every built list item.

    ``extras`` is resolved once per opened title; a failure on one item must
    leave the others, and the item itself, untouched.
    """
    if not extras or not results:
        return
    for result in results:
        try:
            if not isinstance(result, tuple) or len(result) < 3:
                continue
            apply_anime_extras(result[2], extras)
        except Exception as error:
            kodilog(f"[ANIME] extras apply failed: {error}")


def show_seasons_details(params):
    set_content_type("season")

    ids = json.loads(params.get("ids", "{}"))
    mode = params.get("mode", "")
    media_type = params.get("media_type", "")
    anime = truthy_param(params.get("anime"))

    show_season_info(ids, mode, media_type, anime)
    end_of_directory()
    apply_section_view("view.seasons", content_type="seasons")


def show_season_info(ids, mode, media_type, anime=False):
    tmdb_id = ids.get("tmdb_id")
    tvdb_id = ids.get("tvdb_id")
    imdb_id = ids.get("imdb_id")

    if imdb_id:
        res = tmdb_get("find_by_imdb_id", imdb_id)
        if res and res.get("tv_results"):
            tmdb_id = res["tv_results"][0]["id"]

    details = tmdb_get("tv_details", tmdb_id)

    # Callers such as the Nuvio library only know the tmdb_id. Resolve the
    # missing external ids from the details we already fetched, otherwise the
    # episode search carries a bare tmdb_id and sources that match by IMDB
    # (e.g. Torrentio) find nothing. No extra request: "tv_details" already
    # asks TMDB for external_ids.
    external_ids = getattr(details, "external_ids", None) or {}
    if not tvdb_id:
        tvdb_id = external_ids.get("tvdb_id") or tvdb_id
    if not imdb_id:
        imdb_id = external_ids.get("imdb_id") or imdb_id

    ids = {"tmdb_id": tmdb_id, "tvdb_id": tvdb_id, "imdb_id": imdb_id}

    name = details.name
    seasons = details.seasons
    fanart_details = get_fanart_details(tvdb_id=tvdb_id, mode=mode)

    # Anime extras cost one AniList request per opened title. Resolved once here
    # and reused for every season item; failures leave the items untouched.
    extras = _anime_extras(ids, mode, media_type) if anime else None

    results = execute_thread_pool_collection(
        seasons,
        _process_season,
        details,
        name,
        ids,
        mode,
        media_type,
        fanart_details,
        anime,
    )

    # Sort by season number
    results.sort(key=lambda x: x[0])
    _apply_anime_extras(results, extras)

    add_directory_items_batch(
        [(url, list_item, True) for _, url, list_item in results if list_item is not None]
    )


def _process_season(season, details, name, ids, mode, media_type, fanart_details, anime=False):
    season_name = season.name
    overview = season.overview
    if not overview:
        season.update({"overview": getattr(details, "overview", "")})

    if "Miniseries" in season_name:
        season_name = "Season 1"

    season_number = season.season_number
    if season_number == 0 and not get_setting("include_tvshow_specials"):
        return  # skip specials if disabled

    list_item = make_list_item(label=season_name)
    set_media_infoTag(list_item, data=season, fanart_data=fanart_details, mode="season")
    list_item.setProperty("IsPlayable", "false")

    context_menu = add_tmdb_show_context_menu(mode, ids)
    if is_trakt_auth():
        context_menu += add_trakt_watched_context_menu("shows", season=season_number, ids=ids)
    list_item.addContextMenuItems(context_menu)

    url = build_url(
        "show_episodes_details",
        tv_name=name,
        ids=ids,
        mode=mode,
        media_type=media_type,
        season=season_number,
        anime="1" if anime else "0",
    )

    return (season_number, url, list_item)


def show_episodes_details(params):
    set_content_type("episode")

    tv_name = params.get("tv_name", "")
    season = int(params.get("season", 1))
    ids = json.loads(params.get("ids", "{}"))
    mode = params.get("mode", "")
    media_type = params.get("media_type", "")
    anime = truthy_param(params.get("anime"))

    kodilog(
        f"[EPISODES] show_episodes_details: tv_name={tv_name!r}, season={season}, "
        f"mode={mode!r}, media_type={media_type!r}, ids={ids}"
    )
    item_count = show_episode_info(tv_name, season, ids, mode, media_type, anime)
    kodilog(f"[EPISODES] show_episodes_details: added item_count={item_count}")
    end_of_directory()
    kodilog("[EPISODES] show_episodes_details: end_of_directory called")
    apply_section_view("view.episodes", content_type="episodes")


def show_episode_info(tv_name, season, ids, mode, media_type, anime=False):
    season_details = tmdb_get("season_details", {"id": ids.get("tmdb_id"), "season": season})
    if not season_details:
        kodilog(
            f"[EPISODES] show_episode_info: no season_details for "
            f"tmdb_id={ids.get('tmdb_id')}, season={season}"
        )
        return 0

    episodes = getattr(season_details, "episodes", []) or []
    kodilog(
        f"[EPISODES] show_episode_info: fetched episodes_count={len(episodes)} "
        f"for tmdb_id={ids.get('tmdb_id')}, season={season}"
    )
    fanart_details = get_fanart_details(tvdb_id=ids.get("tvdb_id"), mode=mode)

    # Resolved once before the per-episode work and reused for every episode.
    extras = _anime_extras(ids, mode, media_type) if anime else None

    results = execute_thread_pool_collection(
        episodes,
        _process_episode,
        tv_name,
        season,
        ids,
        mode,
        media_type,
        fanart_details,
        anime,
    )

    # Sort by episode number
    results.sort(key=lambda x: x[0])
    item_count = len([list_item for _, _, list_item in results if list_item is not None])
    kodilog(
        f"[EPISODES] show_episode_info: processed results_count={len(results)}, "
        f"item_count={item_count}"
    )
    _apply_anime_extras(results, extras)

    add_directory_items_batch(
        [(url, list_item, False) for _, url, list_item in results if list_item is not None]
    )
    return item_count


def _process_episode(episode, tv_name, season, ids, mode, media_type, fanart_details, anime=False):
    ep_name = episode.name
    episode_number = episode.episode_number

    tv_data = {
        "name": quote(ep_name),
        "episode": episode_number,
        "season": season,
        # Travels with the search request so the anime route can match TMDB numbering
        # against an episode index that carries original air dates.
        "air_date": getattr(episode, "air_date", None),
    }

    list_item = make_list_item(label=f"{season}x{episode_number}. {ep_name}")
    list_item.setProperty("IsPlayable", "true")
    list_item.setProperty("jacktook.simkl.tmdb_id", str(ids.get("tmdb_id", "")))
    list_item.setProperty("jacktook.simkl.media_type", "episode")
    list_item.setProperty("jacktook.simkl.season", str(season))
    list_item.setProperty("jacktook.simkl.episode", str(episode_number))
    set_media_infoTag(list_item, data=episode, fanart_data=fanart_details, mode="episode")

    context_menu = add_tmdb_episode_context_menu(mode, tv_name, tv_data, ids, anime=anime)
    if is_trakt_auth():
        context_menu += add_trakt_watched_context_menu(
            "shows", season=season, episode=episode_number, ids=ids
        )
    context_menu += add_simkl_history_context_menu(
        "episode", ids.get("tmdb_id"), season, episode_number
    )
    context_menu += add_nuvio_history_context_menu(
        "episode", ids.get("tmdb_id"), season, episode_number, title=tv_name
    )
    list_item.addContextMenuItems(context_menu)

    url = build_url(
        "search",
        mode=mode,
        media_type=media_type,
        query=tv_name,
        ids=ids,
        tv_data=tv_data,
        anime="1" if anime else "0",
    )

    return (episode_number, url, list_item)
