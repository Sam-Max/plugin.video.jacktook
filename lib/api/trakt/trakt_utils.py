from datetime import datetime
import random
import re
import time
import json
import xbmc
from lib.utils.kodi.utils import action_url_run, kodilog
from lib.utils.kodi.settings import get_setting


def is_trakt_auth():
    if not get_setting("is_trakt_auth"):
        kodilog("Trakt is not authenticated", level=xbmc.LOGDEBUG)
        return False
    kodilog("Trakt is authenticated", level=xbmc.LOGDEBUG)
    return True


def add_trakt_watchlist_context_menu(media_type, ids):
    filtered_ids = clean_ids(
        {
            "tmdb": ids.get("tmdb_id") or ids.get("tmdb"),
            "tvdb": ids.get("tvdb_id") or ids.get("tvdb"),
            "imdb": ids.get("imdb_id") or ids.get("imdb"),
        }
    )
    return [
        (
            "Add to Trakt Watchlist",
            action_url_run(
                "trakt_add_to_watchlist",
                media_type=media_type,
                ids=json.dumps(filtered_ids),
            ),
        ),
        (
            "Remove from Trakt Watchlist",
            action_url_run(
                "trakt_remove_from_watchlist",
                media_type=media_type,
                ids=json.dumps(filtered_ids),
            ),
        ),
    ]


def add_trakt_watched_context_menu(media_type, season=None, episode=None, ids={}):
    filtered_ids = clean_ids(
        {
            "tmdb": ids.get("tmdb_id") or ids.get("tmdb"),
            "tvdb": ids.get("tvdb_id") or ids.get("tvdb"),
            "imdb": ids.get("imdb_id") or ids.get("imdb"),
        }
    )
    return [
        (
            "Mark as Watched on Trakt",
            action_url_run(
                "trakt_mark_as_watched",
                media_type=media_type,
                ids=json.dumps(filtered_ids),
                season=json.dumps(season),
                episode=json.dumps(episode),
            ),
        ),
        (
            "Mark as Unwatched on Trakt",
            action_url_run(
                "trakt_mark_as_unwatched",
                media_type=media_type,
                ids=json.dumps(filtered_ids),
                season=json.dumps(season),
                episode=json.dumps(episode),
            ),
        ),
    ]


def clean_ids(ids_dict):
    return {k: v for k, v in ids_dict.items() if v not in (None, "", "null")}


def jsondate_to_datetime(jsondate_object, resformat, remove_time=False):
    if not jsondate_object:
        return None
    if remove_time:
        datetime_object = datetime_workaround(jsondate_object, resformat).date()
    else:
        datetime_object = datetime_workaround(jsondate_object, resformat)
    return datetime_object


def datetime_workaround(data, str_format):
    try:
        datetime_object = datetime.strptime(data, str_format)
    except:
        datetime_object = datetime(*(time.strptime(data, str_format)[0:6]))
    return datetime_object


def sort_list(sort_key, sort_direction, list_data):
    try:
        reverse = sort_direction != "asc"
        if sort_key == "rank":
            return sorted(list_data, key=lambda x: x["rank"], reverse=reverse)
        if sort_key == "added":
            return sorted(list_data, key=lambda x: x["listed_at"], reverse=reverse)
        if sort_key == "title":
            return sorted(
                list_data,
                key=lambda x: title_key(x[x["type"]].get("title")),
                reverse=reverse,
            )
        if sort_key == "released":
            return sorted(
                list_data, key=lambda x: released_key(x[x["type"]]), reverse=reverse
            )
        if sort_key == "runtime":
            return sorted(
                list_data, key=lambda x: x[x["type"]].get("runtime", 0), reverse=reverse
            )
        if sort_key == "popularity":
            return sorted(
                list_data, key=lambda x: x[x["type"]].get("votes", 0), reverse=reverse
            )
        if sort_key == "percentage":
            return sorted(
                list_data, key=lambda x: x[x["type"]].get("rating", 0), reverse=reverse
            )
        if sort_key == "votes":
            return sorted(
                list_data, key=lambda x: x[x["type"]].get("votes", 0), reverse=reverse
            )
        if sort_key == "random":
            return sorted(list_data, key=lambda k: random.random())
        return list_data
    except:
        return list_data


def released_key(item):
    if "released" in item:
        return item["released"] or "2050-01-01"
    if "first_aired" in item:
        return item["first_aired"] or "2050-01-01"
    return "2050-01-01"


def title_key(title):
    try:
        if title is None:
            title = ""
        articles = ["the", "a", "an"]
        match = re.match(r"^((\w+)\s+)", title.lower())
        if match and match.group(2) in articles:
            offset = len(match.group(1))
        else:
            offset = 0
        return title[offset:]
    except:
        return title


def sort_for_article(_list, _key):
    _list.sort(key=lambda k: re.sub(r"(^the |^a |^an )", "", k[_key].lower()))
    return _list
