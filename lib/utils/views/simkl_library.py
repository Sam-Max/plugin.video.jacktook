from xbmc import executebuiltin
from xbmcplugin import setContent

from lib.api.simkl import SimklClient, is_simkl_authenticated
from lib.utils.general.utils import build_list_item
from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    action_url_run,
    add_directory_items_batch,
    apply_section_view,
    build_url,
    end_of_directory,
    make_list_item,
    notification,
    translation,
)

STATUS_LABELS = {
    "plantowatch": 90983,
    "watching": 90984,
    "completed": 90985,
    "hold": 90986,
    "dropped": 90987,
}


def has_simkl_library_items():
    return is_simkl_authenticated()


def _status_label(status):
    return translation(STATUS_LABELS[status])


def show_simkl_library(_params):
    if not is_simkl_authenticated():
        return
    entries = []
    for media_type, label in (("movies", translation(90008)), ("shows", translation(90007))):
        list_item = build_list_item(label, "simkl.png")
        list_item.getVideoInfoTag().setTitle(label)
        entries.append(
            (build_url("simkl_library_statuses", media_type=media_type), list_item, True)
        )
    add_directory_items_batch(entries)
    end_of_directory(cache=False)


def show_simkl_library_statuses(params):
    if not is_simkl_authenticated():
        return
    media_type = params.get("media_type")
    entries = []
    for status in SimklClient.allowed_library_statuses(media_type):
        label = _status_label(status)
        list_item = build_list_item(label, "simkl.png")
        list_item.getVideoInfoTag().setTitle(label)
        entries.append(
            (
                build_url("simkl_library_items", media_type=media_type, status=status),
                list_item,
                True,
            )
        )
    add_directory_items_batch(entries)
    end_of_directory(cache=False)


def _status_context_menu(media_type, tmdb_id, current_status):
    return [
        (
            translation(90988) % _status_label(status),
            action_url_run(
                "simkl_move_to_status", media_type=media_type, tmdb_id=tmdb_id, status=status
            ),
        )
        for status in SimklClient.allowed_library_statuses(media_type)
        if status != current_status
    ]


def show_simkl_library_items(params):
    if not is_simkl_authenticated():
        return
    media_type, status = params.get("media_type"), params.get("status")
    if status not in SimklClient.allowed_library_statuses(media_type):
        return
    setContent(ADDON_HANDLE, "movies" if media_type == "movies" else "tvshows")
    directory_items = []
    for item in SimklClient().get_library_items(media_type, status):
        list_item = make_list_item(label=item["query"])
        list_item.getVideoInfoTag().setTitle(item["query"])
        tmdb_id = item["ids"]["tmdb_id"]
        list_item.addContextMenuItems(_status_context_menu(media_type, tmdb_id, status))
        if media_type == "movies":
            url, is_folder = (
                build_url("search", mode="movies", query=item["query"], ids=item["ids"]),
                False,
            )
        else:
            url, is_folder = (
                build_url("show_seasons_details", ids=item["ids"], mode="tv", media_type="tv"),
                True,
            )
        directory_items.append((url, list_item, is_folder))
    add_directory_items_batch(directory_items)
    end_of_directory(cache=False)
    apply_section_view("view.movies" if media_type == "movies" else "view.tvshows")


def move_simkl_item_to_status(params):
    if not is_simkl_authenticated():
        return
    media_type, status = params.get("media_type"), params.get("status")
    if SimklClient().move_to_library_status(media_type, params.get("tmdb_id"), status) != status:
        notification(translation(90990), time=3000)
        return
    notification(translation(90989), time=3000)
    executebuiltin("Container.Refresh")
