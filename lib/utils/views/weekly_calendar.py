from datetime import datetime, date
import os
import re
from lib.clients.tmdb.utils.utils import tmdb_get
from lib.db.pickle_db import PickleDatabase
from lib.jacktook.utils import kodilog
from lib.utils.kodi.utils import ADDON_HANDLE, ADDON_PATH, build_url, translation
from lib.utils.general.utils import (
    execute_thread_pool,
    set_media_infoTag,
    set_pluging_category,
    translate_weekday,
)

from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem, endOfDirectory


def show_weekly_calendar():
    set_pluging_category(translation(90021))

    tv_shows = [
        (title, data)
        for title, data in PickleDatabase().get_key("jt:lth").items()
        if data.get("mode") == "tv"
    ]

    results = []

    def fetch_episodes_for_show(item):
        title, data = item
        episodes, details = get_episodes_for_show(data.get("ids"))
        for ep in episodes:
            air_date = ep.get("air_date")
            if air_date and is_this_week(air_date):
                results.append((title, data, ep, details))

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
        tv_data = {"name": title, "episode": ep["number"], "season": ep["season"]}

        # Get the day of the week from air_date
        air_date_obj = parse_date_str(ep["air_date"])
        weekday_name = air_date_obj.strftime("%A")
        weekday_name_translated = translate_weekday(weekday_name)

        # Mark if episode is released today
        is_today = ep["air_date"] == today_str
        mark = (
            f"[UPPERCASE][COLOR=orange]TODAY- [/COLOR][/UPPERCASE]" if is_today else ""
        )

        ep_title = f"{mark}{weekday_name_translated} - ({ep['air_date']}) - {title} - S{ep['season']:02}E{ep['number']:02}"

        list_item = ListItem(label=ep_title)
        list_item.setProperty("IsPlayable", "true")

        set_media_infoTag(list_item, data=details, mode=data.get("mode"))

        addDirectoryItem(
            ADDON_HANDLE,
            build_url(
                "search",
                mode=data.get("mode"),
                media_type=data.get("mode"),
                query=title,
                ids=data.get("ids"),
                tv_data=tv_data,
            ),
            list_item,
            isFolder=False,
        )

    endOfDirectory(ADDON_HANDLE)


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
