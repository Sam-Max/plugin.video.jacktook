import os
import time
from threading import Thread

from xbmcplugin import setContent

from lib.api.nuvio import NuvioClient, is_nuvio_progress_sync_enabled
from lib.clients.tmdb.utils.utils import tmdb_get
from lib.utils.general.utils import (
    format_season_episode,
    set_media_infoTag,
    set_pluging_category,
)
from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    ADDON_PATH,
    action_url_run,
    add_directory_items_batch,
    apply_section_view,
    build_url,
    dialogyesno,
    end_of_directory,
    kodilog,
    make_list_item,
    notification,
    refresh,
    translation,
)


def has_nuvio_history_items():
    return is_nuvio_progress_sync_enabled()


def show_nuvio_history():
    set_pluging_category("Nuvio History")
    setContent(ADDON_HANDLE, "videos")
    directory_items = []
    for item in NuvioClient().get_watched_history():
        title = item["title"]
        label = title
        if item["mode"] == "tv":
            episode_label = format_season_episode(item["season"], item["episode"])
            if episode_label:
                label = f"{title} {episode_label}" if title else episode_label

        try:
            details = tmdb_get(
                "tv_details" if item["mode"] == "tv" else "movie_details",
                item["tmdb_id"],
            )
        except Exception:
            details = None

        # Some entries carry no title (pushed from here or another device), so
        # fall back to the TMDB name before rendering a blank row.
        if not label and details:
            fallback = details.get("name") or details.get("title")
            if fallback:
                label = str(fallback)

        list_item = make_list_item(label=label)
        if details:
            set_media_infoTag(list_item, data=details, mode=item["mode"])
        else:
            list_item.setArt({"icon": os.path.join(ADDON_PATH, "resources", "img", "magnet.png")})
        info_tag = list_item.getVideoInfoTag()
        info_tag.setTitle(label)

        if item["mode"] == "tv":
            url = build_url(
                "show_seasons_details",
                ids={"tmdb_id": str(item["tmdb_id"])},
                mode="tv",
                media_type="tv",
            )
            is_folder = True
        else:
            url = build_url(
                "search",
                mode="movies",
                media_type="movies",
                query=label,
                ids={"tmdb_id": str(item["tmdb_id"])},
            )
            is_folder = False
        context_menu = _nuvio_history_remove_context_menu(item)
        if context_menu:
            list_item.addContextMenuItems(context_menu)
        directory_items.append((url, list_item, is_folder))
    add_directory_items_batch(directory_items)
    end_of_directory(cache=False)
    apply_section_view("view.history", content_type="videos")

    if not directory_items:
        notification(translation(91026), time=3000)


def _nuvio_history_remove_context_menu(item):
    """Build the single-remove context entry for one rendered history row."""
    tmdb_id = NuvioClient._positive_integer(item.get("tmdb_id"))
    if not tmdb_id:
        return []
    media_type = "episode" if item.get("mode") == "tv" else "movie"
    params = {"operation": "remove", "media_type": media_type, "tmdb_id": tmdb_id}
    if media_type == "episode":
        season = NuvioClient._positive_integer(item.get("season"))
        episode = NuvioClient._positive_integer(item.get("episode"))
        if season is None or episode is None:
            return []
        params.update({"season": season, "episode": episode})
    return [(translation(91045), action_url_run("nuvio_update_history", **params))]


def _push_nuvio_watched(item):
    """Push one watched item on a worker thread; never raises into the UI."""
    try:
        if NuvioClient().push_watched_items(items=[item]):
            notification(translation(91046), time=3000)
            refresh()
            return
    except Exception as error:
        kodilog(f"[NUVIO] watched history push failed ({type(error).__name__})")
    notification(translation(91048), time=3000)


def _delete_nuvio_watched(keys):
    """Delete one watched key on a worker thread; never raises into the UI."""
    try:
        if NuvioClient().delete_watched_items(keys=keys):
            notification(translation(91047), time=3000)
            refresh()
            return
    except Exception as error:
        kodilog(f"[NUVIO] watched history delete failed ({type(error).__name__})")
    notification(translation(91048), time=3000)


def update_nuvio_history(params):
    """Handle mark-watched / mark-unwatched context actions for Nuvio."""
    if not isinstance(params, dict):
        return
    operation = params.get("operation")
    media_type = params.get("media_type")
    if operation not in ("add", "remove") or media_type not in ("movie", "episode"):
        return
    tmdb_id = NuvioClient._positive_integer(params.get("tmdb_id"))
    if not tmdb_id:
        return
    content_id = f"tmdb:{tmdb_id}"
    season = episode = None
    if media_type == "episode":
        season = NuvioClient._positive_integer(params.get("season"))
        episode = NuvioClient._positive_integer(params.get("episode"))
        if season is None or episode is None:
            return
    if operation == "remove":
        if not dialogyesno(translation(91049), translation(91050)):
            return
        keys = [{"content_id": content_id}]
        if media_type == "episode":
            keys[0].update({"season": season, "episode": episode})
        thread = Thread(target=_delete_nuvio_watched, args=(keys,))
    else:
        item = {
            "content_id": content_id,
            "content_type": "series" if media_type == "episode" else "movie",
            "watched_at": int(time.time() * 1000),
        }
        title = params.get("title")
        if isinstance(title, str) and title.strip():
            item["title"] = title.strip()
        if media_type == "episode":
            item.update({"season": season, "episode": episode})
        thread = Thread(target=_push_nuvio_watched, args=(item,))
    thread.daemon = True
    thread.start()
