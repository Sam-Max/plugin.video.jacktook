from xbmc import executebuiltin
from xbmcplugin import setContent

from lib.api.simkl import SimklClient, is_simkl_authenticated
from lib.utils.general.utils import format_season_episode, set_pluging_category
from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    add_directory_items_batch,
    apply_section_view,
    build_url,
    end_of_directory,
    make_list_item,
)


def has_simkl_continue_watching_items():
    return is_simkl_authenticated()


def show_simkl_continue_watching():
    set_pluging_category("Simkl Continue Watching")
    setContent(ADDON_HANDLE, "videos")
    directory_items = []
    for item in SimklClient().get_playback():
        label = item["query"]
        if item["mode"] == "tv":
            episode_label = format_season_episode(
                item["tv_data"]["season"], item["tv_data"]["episode"]
            )
            label = f"{label} {episode_label}"
        list_item = make_list_item(label=label)
        list_item.getVideoInfoTag().setTitle(label)
        list_item.setProperty("PercentPlayed", str(item["simkl_resume_progress"]))
        list_item.setProperty("IsPlayable", "true")
        list_item.addContextMenuItems(
            [
                (
                    "Discard Simkl Resume",
                    "RunPlugin("
                    f"{build_url('simkl_discard_playback', session_id=item['simkl_session_id'])}"
                    ")",
                )
            ]
        )
        directory_items.append((build_url("simkl_resume", **item), list_item, False))
    add_directory_items_batch(directory_items)
    end_of_directory(cache=False)
    apply_section_view("view.history", content_type="videos")


def discard_simkl_playback(params):
    if SimklClient().delete_playback(params.get("session_id")):
        executebuiltin("Container.Refresh")
