from datetime import datetime, date, timedelta
from copy import copy
import os
import re

from lib.clients.tmdb.utils.utils import tmdb_get
from lib.db.pickle_db import PickleDatabase
from lib.jacktook.utils import kodilog
from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    ADDON_PATH,
    build_url,
    end_of_directory,
    translation,
    kodi_play_media,
)
from lib.utils.general.utils import (
    execute_thread_pool,
    set_media_infoTag,
    set_pluging_category,
    translate_weekday,
)
from lib.utils.kodi.utils import get_setting

from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem


def show_weekly_calendar(library=False):
    set_pluging_category(translation(90021))

    if library:
        source_dict = PickleDatabase().get_key("jt:lib")
    else:
        source_dict = PickleDatabase().get_key("jt:lth")

    tv_shows = [
        (title, data) for title, data in source_dict.items() if data.get("mode") == "tv"
    ]

    results = []

    # Broadcast Day Adjustment logic
    # This is a manual simulation of broadcast times, not real timezone handling.
    use_broadcast_adjustment = get_setting("use_broadcast_adjustment", False)
    broadcast_offset = int(get_setting("broadcast_offset", 0))

    def calculate_adjusted_broadcast(date_str, offset_hours):
        """
        Calculates an adjusted date and time based on a manual hour offset.
        Assumes the original air time is midnight (00:00).
        """
        if not date_str:
            return None, None

        try:
            # Parse date, assume midnight (00:00) for calculation
            dt = datetime.strptime(date_str, "%Y-%m-%d")

            if use_broadcast_adjustment:
                # Clamp offset to -24 to +24 (defensive, though settings limit this)
                offset = max(-24, min(24, offset_hours))
                dt += timedelta(hours=offset)

            return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")
        except Exception as e:
            kodilog(f"Error calculating broadcast adjustment: {e}")
            return date_str, "00:00"

    def fetch_episodes_for_show(item):
        title, data = item
        episodes, details = get_episodes_for_show(data.get("ids"))
        for ep in episodes:
            # create a shallow copy to avoid mutating the cached data
            ep_copy = copy(ep)

            original_air_date = ep_copy.get("air_date")
            adjusted_date, adjusted_time = calculate_adjusted_broadcast(
                original_air_date, broadcast_offset
            )

            # Attach adjusted values for display
            ep_copy["air_date"] = adjusted_date
            ep_copy["air_time"] = adjusted_time

            if adjusted_date and is_this_week(adjusted_date):
                results.append((title, data, ep_copy, details))

    # Use thread pool to fetch episodes in parallel
    execute_thread_pool(tv_shows, fetch_episodes_for_show)

    # Add fixed item showing current date at the top
    current_date = datetime.now().strftime("%A, %d %B %Y")
    date_item = ListItem(
        label=f"[UPPERCASE][COLOR=orange]Today: {current_date}[/COLOR][/UPPERCASE]"
    )
    date_item.setArt(
        {"icon": os.path.join(ADDON_PATH, "resources", "img", "history.png")}
    )
    addDirectoryItem(ADDON_HANDLE, "", date_item, isFolder=False)

    today_str = datetime.now().strftime("%Y-%m-%d")

    results_today = [r for r in results if r[2].get("air_date") == today_str]
    results_other = [r for r in results if r[2].get("air_date") != today_str]

    results = sorted(results_today, key=lambda x: x[2].get("air_date", "")) + sorted(
        results_other, key=lambda x: x[2].get("air_date", "")
    )

    # Add items to Kodi UI
    for (
        title,
        data,
        ep,
        details,
    ) in results:
        # Get episode name if available
        ep_name = ep.get("name", "")

        # Build complete IDs if possible from show details
        ids = copy(data.get("ids", {}))
        external_ids = getattr(details, "external_ids", {})
        if external_ids:
            if external_ids.get("imdb_id"):
                ids["imdb_id"] = external_ids.get("imdb_id")
            if external_ids.get("tvdb_id"):
                ids["tvdb_id"] = external_ids.get("tvdb_id")

        tv_data = {
            "name": ep_name or title,
            "episode": ep["number"],
            "season": ep["season"],
        }

        # Get the day of the week from air_date
        air_date_obj = parse_date_str(ep["air_date"])
        weekday_name = air_date_obj.strftime("%A")
        weekday_name_translated = translate_weekday(weekday_name)

        # Mark if episode is released today
        is_today = ep["air_date"] == today_str
        mark = (
            f"[UPPERCASE][COLOR=orange]TODAY- [/COLOR][/UPPERCASE]" if is_today else ""
        )

        ep_title = f"{mark}{weekday_name_translated} - ({ep['air_date']} {ep.get('air_time', '00:00')}) - {title} - S{ep['season']:02}E{ep['number']:02}"

        list_item = ListItem(label=ep_title)
        list_item.setProperty("IsPlayable", "true")

        set_media_infoTag(list_item, data=details, mode=data.get("mode"))

        # Add context menu items
        list_item.addContextMenuItems(
            [
                (
                    translation(90049),
                    kodi_play_media(
                        name="search",
                        mode=data.get("mode"),
                        query=title,
                        ids=ids,
                        tv_data=tv_data,
                        rescrape=True,
                    ),
                ),
            ]
        )

        addDirectoryItem(
            ADDON_HANDLE,
            build_url(
                "search",
                mode=data.get("mode"),
                media_type=data.get("mode"),
                query=title,
                ids=ids,
                tv_data=tv_data,
            ),
            list_item,
            isFolder=False,
        )

    end_of_directory(cache=False)


def get_episodes_for_show(ids):
    tmdb_id = ids.get("tmdb_id")

    try:
        show_details = tmdb_get("tv_details", tmdb_id)
        seasons = getattr(show_details, "seasons")
        seasons = [s for s in seasons if s.get("season_number", 0) > 0]
        if not seasons:
            return [], show_details
        latest_season = max(seasons, key=lambda s: s.get("season_number", 0))
        season_number = latest_season.get("season_number")
        season_details = tmdb_get(
            "season_details", {"id": tmdb_id, "season": season_number}
        )

        episodes = []
        for ep in getattr(season_details, "episodes"):
            air_date = ep.get("air_date")
            if air_date:
                episodes.append(
                    {
                        "season": season_number,
                        "number": ep.get("episode_number"),
                        "air_date": air_date,
                        "name": ep.get("name"),
                    }
                )
        return episodes, show_details
    except Exception as e:
        kodilog(f"Error fetching episodes for TMDB ID {tmdb_id}: {e}")
        return {}, []


def is_this_week(date_str):
    """Check if the date_str (YYYY-MM-DD) is in the current week."""
    try:
        d = parse_date_str(date_str)
        today = date.today()
        year, week, _ = today.isocalendar()
        d_year, d_week, _ = d.isocalendar()
        return (d_year, d_week) == (year, week)
    except Exception as e:
        kodilog(f"Error: {str(e)}")


def parse_date_str(date_str: str) -> date:
    """Parse a date string (YYYY-MM-DD or similar) into a date object without using datetime.strptime."""
    date_str_cleaned = date_str.strip().split("T")[0]
    match = re.search(r"(\d{4})[\-\/]?(\d{1,2})[\-\/]?(\d{1,2})", date_str_cleaned)
    if match:
        year, month, day = map(int, match.groups())
        return date(year, month, day)
    else:
        raise ValueError(f"Invalid date format: {date_str}")
