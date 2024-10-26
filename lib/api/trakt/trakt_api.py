# -*- coding: utf-8 -*-
import json
import random
from threading import Thread
import time
import requests
from lib.api.jacktook.kodi import kodilog
from lib.api.trakt.lists_cache import lists_cache
from lib.api.trakt.base_cache import BASE_DELETE, connect_database
from lib.api.trakt.lists_cache import lists_cache_object
from lib.api.trakt.main_cache import cache_object
from lib.api.trakt.trakt_cache import (
    cache_trakt_object,
    clear_trakt_calendar,
    clear_trakt_collection_watchlist_data,
    clear_trakt_favorites,
    clear_trakt_hidden_data,
    clear_trakt_list_contents_data,
    clear_trakt_list_data,
    clear_trakt_recommendations,
    reset_activity,
)
from lib.api.trakt.utils import sort_for_article, sort_list
from lib.utils.kodi_utils import (
    clear_property,
    copy2clip,
    dialog_ok,
    get_datetime,
    get_setting,
    notification,
    set_setting,
    sleep,
)
from lib.utils.settings import lists_sort_order, trakt_client, trakt_secret
from xbmc import Player as player
from lib.api.trakt.utils import jsondate_to_datetime as js2date
from lib.utils.kodi_utils import progressDialog


empty_setting_check = (None, "empty_setting", "")
standby_date = "2050-01-01T01:00:00.000Z"
res_format = "%Y-%m-%dT%H:%M:%S.%fZ"
timeout = 20

API_ENDPOINT = "https://api.trakt.tv/%s"


def no_client_key():
    notification("Please set a valid Trakt Client ID Key")
    return None


def no_secret_key():
    notification("Please set a valid Trakt Client Secret Key")
    return None


def call_trakt(
    path,
    params={},
    data=None,
    is_delete=False,
    with_auth=True,
    method=None,
    pagination=False,
    page_no=1,
):
    def send_query():
        resp = None
        if with_auth:
            try:
                try:
                    expires_at = float(get_setting("trakt.expires"))
                except:
                    expires_at = 0.0
                if time.time() > expires_at:
                    trakt_refresh_token()
            except:
                pass
            token = get_setting("trakt.token")
            if token:
                headers["Authorization"] = "Bearer " + token
        try:
            if method:
                if method == "post":
                    resp = requests.post(
                        API_ENDPOINT % path, headers=headers, timeout=timeout
                    )
                elif method == "delete":
                    resp = requests.delete(
                        API_ENDPOINT % path, headers=headers, timeout=timeout
                    )
                elif method == "sort_by_headers":
                    resp = requests.get(
                        API_ENDPOINT % path,
                        params=params,
                        headers=headers,
                        timeout=timeout,
                    )
            elif data is not None:
                assert not params
                resp = requests.post(
                    API_ENDPOINT % path, json=data, headers=headers, timeout=timeout
                )
            elif is_delete:
                resp = requests.delete(
                    API_ENDPOINT % path, headers=headers, timeout=timeout
                )
            else:
                resp = requests.get(
                    API_ENDPOINT % path, params=params, headers=headers, timeout=timeout
                )
            resp.raise_for_status()
        except Exception as e:
            raise Exception(f"Trakt Error: {str(e)}")
        return resp

    CLIENT_ID = trakt_client()
    if CLIENT_ID in empty_setting_check:
        return no_client_key()
    headers = {
        "Content-Type": "application/json",
        "trakt-api-version": "2",
        "trakt-api-key": CLIENT_ID,
    }
    if pagination:
        params["page"] = page_no
    response = send_query()
    try:
        status_code = response.status_code
    except:
        return None
    if status_code == 401:
        if player().isPlaying() == False:
            if (
                with_auth
                and dialog_ok(
                    heading="Authorize Trakt",
                    line1="You must authenticate with Trakt. Do you want to authenticate now?",
                )
                and trakt_authenticate()
            ):
                response = send_query()
            else:
                pass
        else:
            return
    elif status_code == 429:
        headers = response.headers
        if "Retry-After" in headers:
            time.sleep(1000 * headers["Retry-After"])
            response = send_query()
    response.encoding = "utf-8"
    try:
        result = response.json()
    except:
        return None
    headers = response.headers
    if (
        method == "sort_by_headers"
        and "X-Sort-By" in headers
        and "X-Sort-How" in headers
    ):
        try:
            result = sort_list(headers["X-Sort-By"], headers["X-Sort-How"], result)
        except:
            pass
    if pagination:
        return (result, headers["X-Pagination-Page-Count"])
    else:
        return result


def trakt_get_device_code():
    CLIENT_ID = trakt_client()
    if CLIENT_ID in empty_setting_check:
        return no_client_key()
    data = {"client_id": CLIENT_ID}
    return call_trakt("oauth/device/code", data=data, with_auth=False)


def trakt_get_device_token(device_codes):
    CLIENT_ID = trakt_client()
    if CLIENT_ID in empty_setting_check:
        return no_client_key()
    CLIENT_SECRET = trakt_secret()
    if CLIENT_SECRET in empty_setting_check:
        return no_secret_key()
    result = None
    # try:
    headers = {
        "Content-Type": "application/json",
        "trakt-api-version": "2",
        "trakt-api-key": CLIENT_ID,
    }
    data = {
        "code": device_codes["device_code"],
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    start = time.time()
    expires_in = device_codes["expires_in"]
    sleep_interval = device_codes["interval"]
    user_code = str(device_codes["user_code"])
    try:
        copy2clip(user_code)
    except:
        pass
    content = "[CR]Navigate to: [B]%s[/B][CR]Enter the following code: [B]%s[/B]" % (
        str(device_codes["verification_url"]),
        user_code,
    )
    progressDialog.create("Trakt Authorize")
    progressDialog.update(0, content)
    try:
        time_passed = 0
        while not progressDialog.iscanceled() and time_passed < expires_in:
            sleep(max(sleep_interval, 1) * 1000)
            response = requests.post(
                API_ENDPOINT % "oauth/device/token",
                data=json.dumps(data),
                headers=headers,
                timeout=timeout,
            )
            status_code = response.status_code
            if status_code == 200:
                result = response.json()
                break
            elif status_code == 400:
                time_passed = time.time() - start
                progress = int(100 * time_passed / expires_in)
                progressDialog.update(progress, content)
            else:
                break
    except:
        pass
    try:
        progressDialog.close()
    except:
        pass
    # except:
    #     pass
    return result


def trakt_refresh_token():
    CLIENT_ID = trakt_client()
    if CLIENT_ID in empty_setting_check:
        return no_client_key()
    CLIENT_SECRET = trakt_secret()
    if CLIENT_SECRET in empty_setting_check:
        return no_secret_key()
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
        "grant_type": "refresh_token",
        "refresh_token": get_setting("trakt.refresh"),
    }
    response = call_trakt("oauth/token", data=data, with_auth=False)
    if response:
        set_setting("trakt.token", response["access_token"])
        set_setting("trakt.refresh", response["refresh_token"])
        set_setting("trakt.expires", str(time.time() + 7776000))


def trakt_authenticate():
    code = trakt_get_device_code()
    token = trakt_get_device_token(code)
    if token:
        set_setting("trakt.token", token["access_token"])
        set_setting("trakt.refresh", token["refresh_token"])
        set_setting("trakt.expires", str(time.time() + 7776000))
        sleep(1000)
        try:
            user = call_trakt("/users/me")
            set_setting("trakt.user", str(user["username"]))
        except:
            pass
        notification("Trakt Account Authorized", time=3000)
        trakt_sync_activities(force_update=True)
        return True
    notification("Trakt Error Authorizing", time=3000)
    return False


def trakt_revoke_authentication():
    set_setting("trakt.user", "empty_setting")
    set_setting("trakt.expires", "")
    set_setting("trakt.token", "")
    set_setting("trakt.refresh", "")
    clear_all_trakt_cache_data(refresh=False)
    CLIENT_ID = trakt_client()
    if CLIENT_ID in empty_setting_check:
        return no_client_key()
    CLIENT_SECRET = trakt_secret()
    if CLIENT_SECRET in empty_setting_check:
        return no_secret_key()
    data = {
        "token": get_setting("trakt.token"),
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    call_trakt("oauth/revoke", data=data, with_auth=False)
    notification("You are logged out from Trakt.tv!!", time=3000)


def trakt_movies_trending(page_no):
    string = "trakt_movies_trending_%s" % page_no
    params = {"path": "movies/trending/%s", "params": {"limit": 20}, "page_no": page_no}
    return lists_cache_object(get_trakt, string, params)


def trakt_movies_trending_recent(page_no):
    current_year = get_datetime().year
    years = "%s-%s" % (str(current_year - 1), str(current_year))
    string = "trakt_movies_trending_recent_%s" % page_no
    params = {
        "path": "movies/trending/%s",
        "params": {"limit": 20, "years": years},
        "page_no": page_no,
    }
    return lists_cache_object(get_trakt, string, params)


def trakt_movies_top10_boxoffice():
    string = "trakt_movies_top10_boxoffice"
    params = {"path": "movies/boxoffice/%s", "pagination": False}
    return lists_cache_object(get_trakt, string, params)


def trakt_movies_most_watched(page_no):
    string = "trakt_movies_most_watched_%s" % page_no
    params = {
        "path": "movies/watched/daily/%s",
        "params": {"limit": 20},
        "page_no": page_no,
    }
    return lists_cache_object(get_trakt, string, params)


def trakt_movies_most_favorited(page_no):
    string = "trakt_movies_most_favorited%s" % page_no
    params = {
        "path": "movies/favorited/daily/%s",
        "params": {"limit": 20},
        "page_no": page_no,
    }
    return lists_cache_object(get_trakt, string, params)


def trakt_recommendations(media_type):
    string = "trakt_recommendations_%s" % (media_type)
    params = {
        "path": "/recommendations/%s",
        "path_insert": media_type,
        "with_auth": True,
        "params": {
            "limit": 50,
            "ignore_collected": "true",
            "ignore_watchlisted": "true",
        },
        "pagination": False,
    }
    return cache_trakt_object(get_trakt, string, params)


def trakt_tv_trending(page_no):
    string = "trakt_tv_trending_%s" % page_no
    params = {"path": "shows/trending/%s", "params": {"limit": 20}, "page_no": page_no}
    return lists_cache_object(get_trakt, string, params)


def trakt_tv_trending_recent(page_no):
    current_year = get_datetime().year
    years = "%s-%s" % (str(current_year - 1), str(current_year))
    string = "trakt_tv_trending_recent_%s" % page_no
    params = {
        "path": "shows/trending/%s",
        "params": {"limit": 20, "years": years},
        "page_no": page_no,
    }
    return lists_cache_object(get_trakt, string, params)


def trakt_tv_most_watched(page_no):
    string = "trakt_tv_most_watched_%s" % page_no
    params = {
        "path": "shows/watched/daily/%s",
        "params": {"limit": 20},
        "page_no": page_no,
    }
    return lists_cache_object(get_trakt, string, params)


def trakt_tv_most_favorited(page_no):
    string = "trakt_tv_most_favorited_%s" % page_no
    params = {
        "path": "shows/favorited/daily/%s",
        "params": {"limit": 20},
        "page_no": page_no,
    }
    return lists_cache_object(get_trakt, string, params)


def trakt_anime_trending(page_no):
    string = "trakt_anime_trending_%s" % page_no
    params = {
        "path": "shows/trending/%s",
        "params": {"genres": "anime", "limit": 20},
        "page_no": page_no,
    }
    return lists_cache_object(get_trakt, string, params)


def trakt_anime_trending_recent(page_no):
    current_year = get_datetime().year
    years = "%s-%s" % (str(current_year - 1), str(current_year))
    string = "trakt_anime_trending_recent_%s" % page_no
    params = {
        "path": "shows/trending/%s",
        "params": {"genres": "anime", "limit": 20, "years": years},
        "page_no": page_no,
    }
    return lists_cache_object(get_trakt, string, params)


def trakt_anime_most_watched(page_no):
    string = "trakt_anime_most_watched_%s" % page_no
    params = {
        "path": "shows/watched/daily/%s",
        "params": {"genres": "anime", "limit": 20},
        "page_no": page_no,
    }
    return lists_cache_object(get_trakt, string, params)


def trakt_collection_lists(media_type, list_type):
    limit = 20
    data = trakt_fetch_collection_watchlist("collection", media_type)
    if list_type == "recent":
        data.sort(key=lambda k: k["collected_at"], reverse=True)
    elif list_type == "random":
        random.shuffle(data)
    data = data[:limit]
    return data


def trakt_watchlist_lists(media_type, list_type):
    limit = 20
    data = trakt_fetch_collection_watchlist("watchlist", media_type)
    if list_type == "recent":
        data.sort(key=lambda k: k["collected_at"], reverse=True)
    elif list_type == "random":
        random.shuffle(data)
    data = data[:limit]
    return data


def trakt_watchlist(media_type):
    data = trakt_fetch_collection_watchlist("watchlist", media_type)
    sort_order = lists_sort_order("watchlist")
    if sort_order == 0:
        data = sort_for_article(data, "title")
    elif sort_order == 1:
        data.sort(key=lambda k: k["collected_at"], reverse=True)
    else:
        data.sort(key=lambda k: k.get("released"), reverse=True)
    return data


def trakt_fetch_collection_watchlist(list_type, media_type):
    def _process(params):
        data = get_trakt(params)
        if list_type == "watchlist":
            data = [i for i in data if i["type"] == key]
        return [
            {
                "media_ids": {
                    "tmdb": i[key]["ids"].get("tmdb", ""),
                    "imdb": i[key]["ids"].get("imdb", ""),
                    "tvdb": i[key]["ids"].get("tvdb", ""),
                },
                "title": i[key]["title"],
                "collected_at": i.get(collected_at),
                "released": (
                    i[key].get(r_key)
                    if i[key].get(r_key)
                    else (
                        "2050-01-01"
                        if media_type in ("movie", "movies")
                        else standby_date
                    )
                ),
            }
            for i in data
        ]

    key, r_key, string_insert = (
        ("movie", "released", "movie")
        if media_type in ("movie", "movies")
        else ("show", "first_aired", "tvshow")
    )
    collected_at = (
        "listed_at"
        if list_type == "watchlist"
        else (
            "collected_at" if media_type in ("movie", "movies") else "last_collected_at"
        )
    )
    string = "trakt_%s_%s" % (list_type, string_insert)
    path = "sync/%s/%s?extended=full"
    params = {
        "path": path,
        "path_insert": (list_type, media_type),
        "with_auth": True,
        "pagination": False,
    }
    return cache_trakt_object(_process, string, params)


def trakt_search_lists(search_title, page_no):
    def _process(dummy_arg):
        return call_trakt(
            "search",
            params={
                "type": "list",
                "fields": "name, description",
                "query": search_title,
                "limit": 50,
            },
            pagination=True,
            page_no=page_no,
        )

    string = "trakt_search_lists_%s_%s" % (search_title, page_no)
    return cache_object(_process, string, "dummy_arg", False, 4)


def trakt_favorites(media_type):
    def _process(params):
        return [
            {
                "media_ids": {
                    "tmdb": i[i["type"]]["ids"].get("tmdb", ""),
                    "imdb": i[i["type"]]["ids"].get("imdb", ""),
                    "tvdb": i[i["type"]]["ids"].get("tvdb", ""),
                }
            }
            for i in get_trakt(params)
        ]

    media_type = "movies" if media_type in ("movie", "movies") else "shows"
    string = "trakt_favorites_%s" % media_type
    params = {
        "path": "users/me/favorites/%s/%s",
        "path_insert": (media_type, "title"),
        "with_auth": True,
        "pagination": False,
    }
    return cache_trakt_object(_process, string, params)


def get_trakt_list_contents(list_type, user, slug, with_auth):
    def _process(params):
        return [
            {
                "media_ids": i[i["type"]]["ids"],
                "title": i[i["type"]]["title"],
                "type": i["type"],
                "order": c,
            }
            for c, i in enumerate(get_trakt(params))
            if i["type"] in ("movie", "show")
        ]

    string = "trakt_list_contents_%s_%s_%s" % (list_type, user, slug)
    if user == "Trakt Official":
        params = {
            "path": "lists/%s/items",
            "path_insert": slug,
            "params": {"extended": "full"},
            "method": "sort_by_headers",
        }
    else:
        params = {
            "path": "users/%s/lists/%s/items",
            "path_insert": (user, slug),
            "params": {"extended": "full"},
            "with_auth": with_auth,
            "method": "sort_by_headers",
        }
    return cache_trakt_object(_process, string, params)


def trakt_trending_popular_lists(list_type, page_no):
    string = "trakt_%s_user_lists_%s" % (list_type, page_no)
    params = {
        "path": "lists/%s",
        "path_insert": list_type,
        "params": {"limit": 50},
        "page_no": page_no,
    }
    return cache_object(get_trakt, string, params, False)


def trakt_get_lists(list_type):
    if list_type == "my_lists":
        string = "trakt_my_lists"
        path = "users/me/lists%s"
    elif list_type == "liked_lists":
        string = "trakt_liked_lists"
        path = "users/likes/lists%s"
    params = {
        "path": path,
        "params": {"limit": 1000},
        "pagination": False,
        "with_auth": True,
    }
    return cache_trakt_object(get_trakt, string, params)


def make_trakt_slug(name):
    import re

    name = name.strip()
    name = name.lower()
    name = re.sub("[^a-z0-9_]", "-", name)
    name = re.sub("--+", "-", name)
    return name


def trakt_get_activity():
    params = {"path": "sync/last_activities%s", "with_auth": True, "pagination": False}
    return get_trakt(params)


def get_trakt(params):
    result = call_trakt(
        params["path"] % params.get("path_insert", ""),
        params=params.get("params", {}),
        data=params.get("data"),
        is_delete=params.get("is_delete", False),
        with_auth=params.get("with_auth", False),
        method=params.get("method"),
        pagination=params.get("pagination", True),
        page_no=params.get("page_no"),
    )
    return result[0] if params.get("pagination", True) else result


def trakt_sync_activities(force_update=False):
    def clear_properties(media_type):
        for item in ((True, True), (True, False), (False, True), (False, False)):
            clear_property("1_%s_%s_%s_watched" % (media_type, item[0], item[1]))

    def _get_timestamp(date_time):
        return int(time.mktime(date_time.timetuple()))

    def _compare(latest, cached):
        try:
            result = _get_timestamp(js2date(latest, res_format)) > _get_timestamp(
                js2date(cached, res_format)
            )
        except:
            result = True
        return result

    if force_update:
        clear_all_trakt_cache_data(refresh=False)
    clear_trakt_calendar()
    clear_trakt_list_contents_data("user_lists")
    clear_trakt_list_contents_data("liked_lists")
    clear_trakt_list_contents_data("my_lists")
    if (
        get_setting("trakt.user", "empty_setting") in ("empty_setting", "")
        and not force_update
    ):
        return "no account"
    try:
        latest = trakt_get_activity()
    except:
        return "failed"
    cached = reset_activity(latest)
    if not _compare(latest["all"], cached["all"]):
        return "not needed"
    clear_list_contents, lists_actions = False, []
    cached_movies, latest_movies = cached["movies"], latest["movies"]
    cached_shows, latest_shows = cached["shows"], latest["shows"]
    cached_episodes, latest_episodes = cached["episodes"], latest["episodes"]
    cached_lists, latest_lists = cached["lists"], latest["lists"]
    if _compare(latest["recommendations"], cached["recommendations"]):
        clear_trakt_recommendations()
    if _compare(latest["favorites"], cached["favorites"]):
        clear_trakt_favorites()
    if _compare(latest_movies["collected_at"], cached_movies["collected_at"]):
        clear_trakt_collection_watchlist_data("collection", "movie")
    if _compare(latest_episodes["collected_at"], cached_episodes["collected_at"]):
        clear_trakt_collection_watchlist_data("collection", "tvshow")
    if _compare(latest_movies["watchlisted_at"], cached_movies["watchlisted_at"]):
        clear_trakt_collection_watchlist_data("watchlist", "movie")
    if _compare(latest_shows["watchlisted_at"], cached_shows["watchlisted_at"]):
        clear_trakt_collection_watchlist_data("watchlist", "tvshow")
    if _compare(latest_shows["hidden_at"], cached_shows["hidden_at"]):
        clear_properties("episode")
        clear_trakt_hidden_data("progress_watched")
    if _compare(latest_lists["updated_at"], cached_lists["updated_at"]):
        clear_list_contents = True
        lists_actions.append("my_lists")
    if _compare(latest_lists["liked_at"], cached_lists["liked_at"]):
        clear_list_contents = True
        lists_actions.append("liked_lists")
    if clear_list_contents:
        for item in lists_actions:
            clear_trakt_list_data(item)
            clear_trakt_list_contents_data(item)
    return "success"


def clear_all_trakt_cache_data(refresh=True):
    try:
        dbcon = connect_database("trakt_db")
        for table in ("trakt_data", "progress", "watched", "watched_status"):
            dbcon.execute(BASE_DELETE % table)
        dbcon.execute("VACUUM")
        if refresh:
            Thread(target=trakt_sync_activities).start()
        return True
    except:
        return False


def clear_cache(cache_type):
    success = True
    if cache_type == "trakt":
        success = clear_all_trakt_cache_data()
    elif cache_type == "list":
        success = lists_cache.delete_all_lists()
    if success:
        return success
