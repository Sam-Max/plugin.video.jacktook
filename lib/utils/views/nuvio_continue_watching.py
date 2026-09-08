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


def has_nuvio_continue_watching_items():
    return is_nuvio_progress_sync_enabled()


def show_nuvio_continue_watching():
    set_pluging_category("Nuvio Continue Watching")
    setContent(ADDON_HANDLE, "videos")
    directory_items = []
    for item in NuvioClient().get_watch_progress():
        label = None
        try:
            details = tmdb_get(
                "tv_details" if item["mode"] == "tv" else "movie_details",
                item["tmdb_id"],
            )
        except Exception:
            details = None

        if details:
            title = details.get("title") or details.get("name")
            if title:
                label = str(title)

        episode_label = ""
        if item["mode"] == "tv":
            episode_label = format_season_episode(item["season"], item["episode"])
            if label:
                label = f"{label} {episode_label}"

        if not label:
            label = f"TMDB {item['tmdb_id']}"
            if episode_label:
                label = f"{label} {episode_label}"

        list_item = make_list_item(label=label)
        if details:
            set_media_infoTag(list_item, data=details, mode=item["mode"])
        else:
            list_item.setArt({"icon": os.path.join(ADDON_PATH, "resources", "img", "magnet.png")})

        percent = item["percent"]
        info_tag = list_item.getVideoInfoTag()
        info_tag.setTitle(label)
        info_tag.setResumePoint(percent / 100, 1)
        list_item.setProperty("PercentPlayed", str(percent))
        list_item.setProperty("IsPlayable", "true")
        list_item.addContextMenuItems(
            [
                (
                    translation(91027),
                    "RunPlugin("
                    f"{build_url('nuvio_remove_progress', progress_key=item['progress_key'])}"
                    ")",
                )
            ]
        )

        url_kwargs = {
            "action": "nuvio_resume",
            "mode": item["mode"],
            "media_type": "tv" if item["mode"] == "tv" else "movies",
            "query": label,
            "ids": {"tmdb_id": str(item["tmdb_id"])},
            "nuvio_resume_percent": percent,
        }
        if item["mode"] == "tv":
            url_kwargs["tv_data"] = {
                "season": item["season"],
                "episode": item["episode"],
                "name": label,
            }
        directory_items.append((build_url(**url_kwargs), list_item, False))
    add_directory_items_batch(directory_items)
    end_of_directory(cache=False)
    apply_section_view("view.history", content_type="videos")

    if not directory_items:
        notification(translation(91025), time=3000)
