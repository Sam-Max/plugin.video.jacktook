import json
import os

from xbmc import executebuiltin
from xbmcplugin import setContent

from lib.db.pickle_db import PickleDatabase
from lib.utils.general.utils import (
    Indexer,
    IndexerType,
    format_season_episode,
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
    make_list_item,
    translation,
)
from lib.utils.views.last_files import add_last_files_context_menu, parse_time


def has_continue_watching_items():
    all_items = PickleDatabase().get_key("jt:lfh").items()
    for _title, data in all_items:
        progress = float(data.get("progress", 0))
        if 5 < progress < 90:
            return True
    return False


def remove_continue_watching_item(params):
    title = params.get("title")
    if title:
        PickleDatabase().delete_item(key="jt:lfh", subkey=title)
        executebuiltin("Container.Refresh")


def _source_label(data):
    """Best-effort human-readable source class for a stored playback payload."""
    indexer = data.get("indexer", "")
    name = data.get("name", "")
    if indexer in (Indexer.JACKGRAM, Indexer.TELEGRAM) or name in (
        Indexer.JACKGRAM,
        Indexer.TELEGRAM,
    ):
        return str(indexer or name)
    if data.get("indexer") == Indexer.EASYNEWS:
        return "Easynews"
    if data.get("debrid_type"):
        return str(data["debrid_type"])
    source_type = data.get("type", "")
    if source_type == IndexerType.STREMIO_DEBRID:
        return "Stremio"
    if source_type == IndexerType.DEBRID:
        return "Debrid"
    if source_type == IndexerType.TORRENT:
        return "Torrent"
    if source_type == IndexerType.DIRECT:
        return "Direct"
    if data.get("is_torrent") or data.get("magnet") or data.get("info_hash"):
        return "Torrent"
    return ""


def show_continue_watching(params=None):
    if params is None:
        params = {}

    set_pluging_category(translation(90200))
    setContent(ADDON_HANDLE, "videos")

    per_page = 10
    page = int(params.get("page", 1))

    all_items = list(reversed(PickleDatabase().get_key("jt:lfh").items()))
    items = sorted(all_items, key=parse_time, reverse=True)

    # Filter by progress before slicing so pages stay dense
    filtered_items = []
    for title, data in items:
        progress = float(data.get("progress", 0))
        if 5 < progress < 90:
            filtered_items.append((title, data))

    total = len(filtered_items)
    start = (page - 1) * per_page
    end = start + per_page
    items = filtered_items[start:end]

    directory_items = []
    for title, data in items:
        tv_data = data.get("tv_data", {})

        label_title = data.get("title", "")

        if tv_data:
            show_name = tv_data.get("name", "")
            episode_label = format_season_episode(tv_data.get("season"), tv_data.get("episode"))
            if episode_label:
                label = f"{show_name or label_title} {episode_label}"
            else:
                label = show_name or label_title
        else:
            label = label_title

        source_label = _source_label(data)
        if source_label:
            label = f"{label} ({source_label})"

        list_item = make_list_item(label=label)

        # Set Art
        icon = os.path.join(ADDON_PATH, "resources", "img", "magnet.png")

        # Try to find art in data
        art = {}
        if data.get("poster"):
            art["poster"] = data.get("poster")
        if data.get("fanart"):
            art["fanart"] = data.get("fanart")
        if not art:
            art["icon"] = icon
        list_item.setArt(art)

        # Set Info
        info_tag = list_item.getVideoInfoTag()
        info_tag.setTitle(label)
        info_tag.setPlot(truncate_text(data.get("overview", "")))

        if "current_time" in data and "total_time" in data:
            try:
                current_time = float(data["current_time"])
                total_time = float(data["total_time"])
                info_tag.setResumePoint(current_time, total_time)
            except ValueError:
                pass

        list_item.setProperty("PercentPlayed", str(progress))

        list_item.setProperty("IsPlayable", "true")
        context_menu = add_last_files_context_menu(data)
        context_menu.append(
            (
                translation(90206),
                f"RunPlugin({build_url('remove_continue_watching', title=title)})",
            )
        )
        list_item.addContextMenuItems(context_menu)

        # url to play
        url = build_url("play_media", data=json.dumps(data))

        directory_items.append((url, list_item, False))

    # "Next Page (N more)"
    if end < total:
        total_pages = -(-total // per_page)
        remaining_pages = total_pages - page
        list_item = make_list_item(label=f"Next Page ({remaining_pages} more)")
        list_item.setArt({"icon": os.path.join(ADDON_PATH, "resources", "img", "nextpage.png")})
        directory_items.append(
            (build_url("continue_watching_menu", page=page + 1), list_item, True)
        )

    add_directory_items_batch(directory_items)

    end_of_directory(cache=False)
    apply_section_view("view.history", content_type="videos")
