from lib.api.tmdbv3api.exceptions import TMDbException
from lib.clients.jackgram import Jackgram
from lib.utils.client_utils import validate_host
from lib.utils.tmdb_utils import tmdb_get

from lib.utils.utils import (
    TMDB_POSTER_URL,
    Indexer,
    add_next_button,
    execute_thread_pool,
    list_item,
    set_content_type,
    set_media_infotag,
)

from lib.utils.kodi_utils import (
    ADDON_HANDLE,
    build_url,
    get_setting,
    notification,
    set_view,
)

from xbmcplugin import addDirectoryItem, endOfDirectory


def check_jackgram_active():
    jackgram_enabled = get_setting("jackgram_enabled")
    if not jackgram_enabled:
        notification("You need to activate Jackgram indexer")
        return False
    return True


def get_telegram_files(params):
    if check_jackgram_active():
        page = int(params.get("page"))
        host = get_setting("jackgram_host")
        if not validate_host(host, Indexer.TELEGRAM):
            return
        jackgram_client = Jackgram(host, notification)
        results = jackgram_client.get_files(page=page)
        execute_thread_pool(results, telegram_files)
        add_next_button("get_telegram_files", page=page)
        endOfDirectory(ADDON_HANDLE)
        set_view("widelist")


def telegram_files(info):
    item = list_item(info["file_name"], icon="trending.png")
    item.setProperty("IsPlayable", "true")
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("play_torrent", data=info),
        item,
        isFolder=False,
    )


def get_telegram_latest(params):
    if check_jackgram_active():
        page = int(params.get("page"))
        host = get_setting("jackgram_host")
        if not validate_host(host, Indexer.TELEGRAM):
            return
        jackgram_client = Jackgram(host, notification)
        results = jackgram_client.get_latest(page=page)
        execute_thread_pool(results, telegram_latest_items)
        add_next_button("get_telegram_latest", page=page)
        endOfDirectory(ADDON_HANDLE)
        set_view("widelist")


def telegram_latest_items(info):
    mode = info["type"]
    title = info["title"]

    if mode == "tv":
        details = tmdb_get("tv_details", info["tmdb_id"])
    else:
        details = tmdb_get("movie_details", info["tmdb_id"])

    tmdb_id = info["tmdb_id"]
    imdb_id = details.external_ids.get("imdb_id")
    tvdb_id = details.external_ids.get("tvdb_id")

    info["ids"] = f"{tmdb_id}, {tvdb_id}, {imdb_id}"

    poster_path = f"{TMDB_POSTER_URL}{details.poster_path or ''}"
    overview = details.overview or ""

    item = list_item(title, poster_path=poster_path, icon="trending.png")
    set_media_infotag(item, mode, title, overview=overview)

    addDirectoryItem(
        ADDON_HANDLE,
        build_url("get_telegram_latest_files", data=info),
        item,
        isFolder=True,
    )


def get_telegram_latest_files(params):
    data = eval(params["data"])
    mode = data["type"]

    set_content_type(mode)
    execute_thread_pool(data["files"], telegram_latest_files, data)
    endOfDirectory(ADDON_HANDLE)


def telegram_latest_files(info, data):
    mode = info["mode"]
    title = info["title"]
    tmdb_id = data["tmdb_id"]

    if mode == "tv":
        try:
            details = tmdb_get(
                "episode_details",
                params={
                    "id": tmdb_id,
                    "season": info["season"],
                    "episode": info["episode"],
                },
            )
            poster_path = TMDB_POSTER_URL + details.still_path
            overview = details.overview or ""
            episode_name = details.name
        except (
            TMDbException
        ):  # Cause of anime tmdb id fails when getting episode details
            poster_path = ""
            overview = ""
            episode_name = ""

        item = list_item(title, poster_path=poster_path)

        set_media_infotag(
            item,
            mode,
            title,
            ids=data["ids"],
            ep_name=episode_name,
            season=info["season"],
            episode=info["episode"],
            overview=overview,
        )
    else:
        details = tmdb_get("movie_details", tmdb_id)
        poster_path = TMDB_POSTER_URL + details.poster_path
        item = list_item(title, poster_path=poster_path)
        overview = details.overview or ""
        set_media_infotag(item, mode, title, ids=data["ids"], overview=overview)

    item.setProperty("IsPlayable", "true")
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("play_torrent", data=info),
        item,
        isFolder=False,
    )
