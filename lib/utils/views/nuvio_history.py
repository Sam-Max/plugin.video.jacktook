import os

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
    add_directory_items_batch,
    apply_section_view,
    build_url,
    end_of_directory,
    make_list_item,
    notification,
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
        directory_items.append((url, list_item, is_folder))
    add_directory_items_batch(directory_items)
    end_of_directory(cache=False)
    apply_section_view("view.history", content_type="videos")

    if not directory_items:
        notification(translation(91025), time=3000)
