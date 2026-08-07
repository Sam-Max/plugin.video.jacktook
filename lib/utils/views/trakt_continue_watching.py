import os

from xbmc import executebuiltin
from xbmcplugin import setContent

from lib.api.trakt.trakt import TraktScrobble
from lib.api.trakt.trakt_utils import is_trakt_auth
from lib.clients.tmdb.utils.utils import tmdb_get
from lib.utils.general.utils import (
    format_season_episode,
    set_media_infoTag,
    set_pluging_category,
    truncate_text,
)
from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    ADDON_PATH,
    add_directory_items_batch,
    apply_section_view,
    build_url,
    end_of_directory,
    get_setting,
    make_list_item,
)


def has_trakt_continue_watching_items():
    return get_setting("trakt_enabled") and is_trakt_auth()


def show_trakt_continue_watching():
    set_pluging_category("Trakt Continue Watching")
    setContent(ADDON_HANDLE, "videos")
    directory_items = []
    for item in TraktScrobble().get_playback():
        label = item["query"]
        if item["mode"] == "tv":
            episode_label = format_season_episode(
                item["tv_data"]["season"], item["tv_data"]["episode"]
            )
            label = f"{label} {episode_label}"
        list_item = make_list_item(label=label)
        try:
            details = tmdb_get(
                "tv_details" if item["mode"] == "tv" else "movie_details",
                item["ids"]["tmdb_id"],
            )
        except Exception:
            details = None

        if details:
            set_media_infoTag(list_item, data=details, mode=item["mode"])
        else:
            list_item.setArt(
                {"icon": os.path.join(ADDON_PATH, "resources", "img", "magnet.png")}
            )

        info_tag = list_item.getVideoInfoTag()
        info_tag.setTitle(label)
        if not details:
            overview = item.get("overview", "")
            info_tag.setPlot(truncate_text(overview) if isinstance(overview, str) else "")
        list_item.setProperty("PercentPlayed", str(item["trakt_resume_progress"]))
        list_item.setProperty("IsPlayable", "true")
        list_item.addContextMenuItems(
            [
                (
                    "Discard Trakt Resume",
                    "RunPlugin("
                    f"{build_url('trakt_discard_playback', playback_id=item['trakt_playback_id'])}"
                    ")",
                )
            ]
        )
        directory_items.append((build_url("trakt_resume", **item), list_item, False))
    add_directory_items_batch(directory_items)
    end_of_directory(cache=False)
    apply_section_view("view.history", content_type="videos")


def discard_trakt_playback(params):
    if TraktScrobble().delete_playback(params.get("playback_id")):
        executebuiltin("Container.Refresh")
