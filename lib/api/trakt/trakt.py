import json
import random
import time
import requests
import xbmc
from lib.api.trakt.lists_cache import lists_cache
from lib.api.trakt.base_cache import BASE_DELETE, connect_database
from lib.api.trakt.lists_cache import lists_cache_object
from lib.api.trakt.main_cache import cache_object
from lib.api.trakt.trakt_cache import cache_trakt_object
from lib.api.trakt.trakt_utils import sort_for_article, sort_list
from lib.utils.kodi.utils import (
    copy2clip,
    get_datetime,
    get_property,
    kodilog,
    notification,
    set_property,
    set_setting,
    sleep,
    progressDialog,
)
from lib.utils.kodi.settings import (
    EMPTY_USER,
    trakt_client,
    trakt_lists_sort_order,
    trakt_secret,
)


class TraktBase:
    def __init__(self):
        self.api_endpoint = "https://api.trakt.tv/%s"
        self.timeout = 20
        self.empty_setting_check = (None, "empty_setting", "")
        self.standby_date = "2050-01-01T01:00:00.000Z"
        self.trakt_user = EMPTY_USER

    def ensure_token_valid(self):
        expires = get_property("trakt_expires")
        refresh_token = get_property("trakt_refresh")
        if expires and refresh_token:
            try:
                expires = float(expires)
                # Refresh if less than 1 hour left
                if expires - time.time() < 3600:
                    self.trakt_refresh = refresh_token
                    self.trakt_refresh_token()
            except Exception as e:
                kodilog(f"Error checking token expiry: {e}")

    def no_client_key(self):
        notification("Please set a valid Trakt Client ID Key")
        return None

    def no_secret_key(self):
        notification("Please set a valid Trakt Client Secret Key")
        return None

    def call_trakt(
        self,
        path,
        params=None,
        data=None,
        is_delete=False,
        with_auth=True,
        method=None,
        pagination=False,
        page_no=1,
    ):
        params = params or {}
        headers = {
            "Content-Type": "application/json",
            "trakt-api-version": "2",
            "trakt-api-key": trakt_client(),
        }

        if headers["trakt-api-key"] in self.empty_setting_check:
            return self.no_client_key()

        if with_auth:
            self.ensure_token_valid()
            token = get_property("trakt_token")
            kodilog("Trakt token: %s" % token)

            if token:
                headers["Authorization"] = f"Bearer {token}"
                kodilog("Trakt token: %s" % token)

        if pagination:
            params["page"] = page_no

        response = self._send_request(path, params, data, headers, is_delete, method)
        kodilog("Trakt response status code: %s" % response.status_code)
        try:
            response.raise_for_status()
        except requests.HTTPError as error:
            status_code = response.status_code
            error_messages = {
                400: "Bad Request",
                401: "Unauthorized",
                403: "Forbidden",
                404: "Not Found",
                429: "Rate Limit Exceeded",
                500: "Internal Server Error",
                503: "Service Unavailable",
                504: "Gateway Timeout",
            }
            error_message = error_messages.get(
                status_code, f"HTTP Error: {status_code}"
            )
            kodilog(f"Trakt API error: {response.text}")
            raise ProviderException(f"Trakt API error: {error_message}")
        except requests.RequestException as error:
            error_message = f"Trakt API error: {error}"
            raise ProviderException(error_message)

        return self._process_response(response, method, pagination)

    def _send_request(self, path, params, data, headers, is_delete, method):
        url = self.api_endpoint % path
        kodilog("Trakt URL: %s" % url)
        if method == "post":
            return requests.post(url, headers=headers, timeout=self.timeout)
        elif method == "delete":
            return requests.delete(url, headers=headers, timeout=self.timeout)
        elif method == "sort_by_headers":
            return requests.get(
                url, params=params, headers=headers, timeout=self.timeout
            )
        elif data is not None:
            return requests.post(url, json=data, headers=headers, timeout=self.timeout)
        elif is_delete:
            return requests.delete(url, headers=headers, timeout=self.timeout)
        else:
            return requests.get(
                url, params=params, headers=headers, timeout=self.timeout
            )

    def _process_response(self, response, method, pagination):
        response.encoding = "utf-8"
        try:
            result = response.json()
            kodilog("Response JSON: %s" % result, level=xbmc.LOGDEBUG)
        except ValueError:
            return None

        if method == "sort_by_headers":
            headers = response.headers
            if "X-Sort-By" in headers and "X-Sort-How" in headers:
                try:
                    result = sort_list(
                        headers["X-Sort-By"], headers["X-Sort-How"], result
                    )
                except Exception:
                    pass

        if pagination:
            return result, response.headers.get("X-Pagination-Page-Count")
        return result

    def get_trakt(self, params):
        try:
            kodilog(f"get_trakt params: {params}")

            path_insert = params.get("path_insert", "")
            if not isinstance(path_insert, (tuple, str)):
                path_insert = (path_insert,)

            kodilog(f"Path: {params['path']}")
            kodilog(f"Path insert: {path_insert}")

            formatted_path = params["path"] % path_insert
            kodilog(f"Formatted path: {formatted_path}")

            result = self.call_trakt(
                formatted_path,
                params=params.get("params", {}),
                data=params.get("data"),
                is_delete=params.get("is_delete", False),
                with_auth=params.get("with_auth", False),
                method=params.get("method"),
                pagination=params.get("pagination", True),
                page_no=params.get("page_no"),
            )

            kodilog(f"Call trakt result: {result}", level=xbmc.LOGDEBUG)
            return result[0] if params.get("pagination", True) else result
        except KeyError as e:
            kodilog(f"KeyError in get_trakt: {e}")
            raise
        except TypeError as e:
            kodilog(f"TypeError in get_trakt: {e}")
            raise

    def trakt_refresh_token(self):
        CLIENT_ID = trakt_client()
        if CLIENT_ID in self.empty_setting_check:
            return self.no_client_key()
        CLIENT_SECRET = trakt_secret()
        if CLIENT_SECRET in self.empty_setting_check:
            return self.no_secret_key()
        data = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
            "grant_type": "refresh_token",
            "refresh_token": self.trakt_refresh,
        }
        response = self.call_trakt("oauth/token", data=data, with_auth=False)
        if response:
            set_property("trakt_token", str(response["access_token"]))
            set_property("trakt_refresh", str(response["refresh_token"]))
            set_property("trakt_expires", str(time.time() + 82800))  # 23 hours

    def get_trakt_id_by_tmdb(self, tmdb_id, media_type="movie"):
        params = {
            "path": "search/tmdb/%s",
            "path_insert": tmdb_id,
            "params": {"type": media_type},
            "with_auth": False,
            "pagination": False,
        }
        kodilog(f"get_trakt_id_by_tmdb params: {params}")
        results = self.get_trakt(params)
        if results and isinstance(results, list) and len(results) > 0:
            try:
                return results[0][media_type]["ids"]["trakt"]
            except (KeyError, IndexError, TypeError):
                return None
        return None


class TraktAuthentication(TraktBase):
    def __init__(self):
        super().__init__()

    def trakt_get_device_code(self):
        CLIENT_ID = trakt_client()
        if CLIENT_ID in self.empty_setting_check:
            return self.no_client_key()
        data = {"client_id": CLIENT_ID}
        return self.call_trakt("oauth/device/code", data=data, with_auth=False)

    def trakt_get_device_token(self, device_codes):
        CLIENT_ID = trakt_client()
        if CLIENT_ID in self.empty_setting_check:
            return self.no_client_key()
        CLIENT_SECRET = trakt_secret()
        if CLIENT_SECRET in self.empty_setting_check:
            return self.no_secret_key()
        result = None
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
        content = (
            "[CR]Navigate to: [B]%s[/B][CR]Enter the following code: [B]%s[/B]"
            % (
                str(device_codes["verification_url"]),
                user_code,
            )
        )
        progressDialog.create("Trakt Authorize")
        progressDialog.update(0, content)
        try:
            time_passed = 0
            while not progressDialog.iscanceled() and time_passed < expires_in:
                sleep(max(sleep_interval, 1) * 1000)
                response = requests.post(
                    self.api_endpoint % "oauth/device/token",
                    data=json.dumps(data),
                    headers=headers,
                    timeout=self.timeout,
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
        return result

    def trakt_authenticate(self):
        code = self.trakt_get_device_code()
        token = self.trakt_get_device_token(code)
        if not token:
            kodilog("Trakt authentication failed, no token received")
            notification("Trakt Error Authorizing", time=3000)
            return False
        set_property("trakt_token", str(token["access_token"]))
        set_property("trakt_refresh", str(token["refresh_token"]))
        set_property("trakt_expires", str(time.time() + 82800))  # 23 hours
        try:
            user = self.call_trakt("users/me")
            set_setting("trakt_user", str(user["username"]))
            set_setting("is_trakt_auth", "true")
            notification("Trakt Account Authorized", time=3000)
            return True
        except:
            kodilog("Trakt user not found, setting to empty user")
            set_setting("is_trakt_auth", "false")
            notification("Trakt Error Authorizing", time=3000)
            return False

    def trakt_revoke_authentication(self):
        kodilog("Revoking Trakt authentication")
        TraktCache().clear_all_trakt_cache_data()
        CLIENT_ID = trakt_client()
        if CLIENT_ID in self.empty_setting_check:
            return self.no_client_key()
        CLIENT_SECRET = trakt_secret()
        if CLIENT_SECRET in self.empty_setting_check:
            return self.no_secret_key()
        data = {
            "token": get_property("trakt_token"),
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        }
        set_property("trakt_token", "")
        set_property("trakt_refresh", "")
        set_property("trakt_expires", "")
        set_setting("trakt_user", EMPTY_USER)
        set_setting("is_trakt_auth", "false")
        self.call_trakt("oauth/revoke", data=data, with_auth=False)
        notification("You are now logged out from Trakt.tv", time=3000)


class TraktMovies(TraktBase):
    def trakt_movies_trending(self, page_no):
        string = "trakt_movies_trending_%s" % page_no
        params = {
            "path": "movies/trending/%s",
            "params": {"limit": 20},
            "page_no": page_no,
        }
        return lists_cache_object(self.get_trakt, string, params)

    def trakt_movies_trending_recent(self, page_no):
        current_year = get_datetime().year
        years = "%s-%s" % (str(current_year - 1), str(current_year))
        string = "trakt_movies_trending_recent_%s" % page_no
        params = {
            "path": "movies/trending/%s",
            "params": {"limit": 20, "years": years},
            "page_no": page_no,
        }
        return lists_cache_object(self.get_trakt, string, params)

    def trakt_movies_top10_boxoffice(self):
        string = "trakt_movies_top10_boxoffice"
        params = {"path": "movies/boxoffice/%s", "pagination": False}
        return lists_cache_object(self.get_trakt, string, params)

    def trakt_movies_most_watched(self, page_no):
        string = "trakt_movies_most_watched_%s" % page_no
        params = {
            "path": "movies/watched/daily/%s",
            "params": {"limit": 20},
            "page_no": page_no,
        }
        return lists_cache_object(self.get_trakt, string, params)

    def trakt_movies_most_favorited(self, page_no):
        string = "trakt_movies_most_favorited%s" % page_no
        params = {
            "path": "movies/favorited/daily/%s",
            "params": {"limit": 20},
            "page_no": page_no,
        }
        return lists_cache_object(self.get_trakt, string, params)

    def trakt_recommendations(self, media_type):
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
        return lists_cache_object(self.get_trakt, string, params)


class TraktTV(TraktBase):
    def trakt_tv_trending(self, page_no):
        string = "trakt_tv_trending_%s" % page_no
        params = {
            "path": "shows/trending/%s",
            "params": {"limit": 20},
            "page_no": page_no,
        }
        return lists_cache_object(self.get_trakt, string, params)

    def trakt_tv_trending_recent(self, page_no):
        current_year = get_datetime().year
        years = "%s-%s" % (str(current_year - 1), str(current_year))
        string = "trakt_tv_trending_recent_%s" % page_no
        params = {
            "path": "shows/trending/%s",
            "params": {"limit": 20, "years": years},
            "page_no": page_no,
        }
        return lists_cache_object(self.get_trakt, string, params)

    def trakt_tv_most_watched(self, page_no):
        string = "trakt_tv_most_watched_%s" % page_no
        params = {
            "path": "shows/watched/daily/%s",
            "params": {"limit": 20},
            "page_no": page_no,
        }
        return lists_cache_object(self.get_trakt, string, params)

    def trakt_tv_most_favorited(self, page_no):
        string = "trakt_tv_most_favorited_%s" % page_no
        params = {
            "path": "shows/favorited/daily/%s",
            "params": {"limit": 20},
            "page_no": page_no,
        }
        return lists_cache_object(self.get_trakt, string, params)

    def trakt_recommendations(self, media_type):
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
        return lists_cache_object(self.get_trakt, string, params)


class TraktAnime(TraktBase):
    def trakt_anime_trending(self, page_no):
        string = "trakt_anime_trending_%s" % page_no
        params = {
            "path": "shows/trending/%s",
            "params": {"genres": "anime", "limit": 20},
            "page_no": page_no,
        }
        return lists_cache_object(self.get_trakt, string, params)

    def trakt_anime_trending_recent(self, page_no):
        current_year = get_datetime().year
        years = "%s-%s" % (str(current_year - 1), str(current_year))
        string = "trakt_anime_trending_recent_%s" % page_no
        params = {
            "path": "shows/trending/%s",
            "params": {"genres": "anime", "limit": 20, "years": years},
            "page_no": page_no,
        }
        return lists_cache_object(self.get_trakt, string, params)

    def trakt_anime_most_watched(self, page_no):
        string = "trakt_anime_most_watched_%s" % page_no
        params = {
            "path": "shows/watched/daily/%s",
            "params": {"genres": "anime", "limit": 20},
            "page_no": page_no,
        }
        return lists_cache_object(self.get_trakt, string, params)


class TraktLists(TraktBase):
    def trakt_watchlist(self, media_type):
        kodilog("Fetching trakt watchlist")
        result = self.trakt_fetch_sorted_list("watchlist", media_type)
        kodilog("Watchlist result: %s" % result, level=xbmc.LOGDEBUG)
        return result

    def add_to_watchlist(self, media_type, ids):
        if media_type in ("movie", "movies"):
            media_type = "movies"
        else:
            media_type = "shows"

        payload = {media_type: [{"ids": {"tmdb": int(ids["tmdb"])}}]}

        return self.call_trakt(
            "sync/watchlist",
            data=payload,
            with_auth=True,
            pagination=False,
        )

    def remove_from_watchlist(self, media_type, ids):
        if media_type in ("movie", "movies"):
            media_type = "movies"
        else:
            media_type = "shows"

        payload = {media_type: [{"ids": {"tmdb": int(ids["tmdb"])}}]}
        return self.call_trakt(
            "sync/watchlist/remove",
            data=payload,
            with_auth=True,
            pagination=False,
        )

    def trakt_watched_history(self, media_type, page_no, sort_type="recent"):
        def _process(params, media_type):
            response = self.get_trakt(params)
            kodilog(f"Response from get_trakt: {response}", level=xbmc.LOGDEBUG)
            history = []
            if media_type == "movies":
                for item in response:
                    if item["type"] == "movie":
                        history.append(
                            {
                                "media_ids": item["movie"]["ids"],
                                "title": item["movie"]["title"],
                                "type": "movie",
                                "watched_at": item.get("watched_at"),
                            }
                        )
            elif media_type == "shows":
                for item in response:
                    if item["type"] == "episode":
                        history.append(
                            {
                                "media_ids": item["show"]["ids"],
                                "title": f"{item['show']['title']} - S{item['episode']['season']}E{item['episode']['number']} - {item['episode']['title']}",
                                "type": "show",
                                "watched_at": item.get("watched_at"),
                                "show_title": item["show"]["title"],
                                "ep_title": item["episode"]["title"],
                                "season": item["episode"]["season"],
                                "episode": item["episode"]["number"],
                            }
                        )
            # --- Sorting logic similar to trakt_fetch_sorted_list ---
            if sort_type == "recent":
                history.sort(key=lambda k: k.get("watched_at") or "", reverse=True)
            elif sort_type == "random":
                random.shuffle(history)
            elif sort_type is None:
                # Default: sort by watched_at descending
                history.sort(key=lambda k: k.get("watched_at") or "", reverse=True)
            return history

        if media_type in ("movie", "movies"):
            media_type = "movies"
        else:
            media_type = "shows"

        params = {
            "path": "sync/history/%s",
            "path_insert": media_type,
            "page_no": page_no,
            "with_auth": True,
        }
        return _process(params, media_type)

    def mark_as_watched(self, media_type, season, episode, ids):
        if media_type in ("movie", "movies"):
            media_type_key = "movies"
            payload = {media_type_key: [{"ids": {"tmdb": int(ids["tmdb"])}}]}
        else:
            media_type_key = "shows"
            show_item = {"ids": {"tmdb": int(ids["tmdb"])}}

            if season:
                show_item["seasons"] = [{"number": int(season)}]

            if season and episode:
                show_item["seasons"] = [
                    {"number": int(season), "episodes": [{"number": int(episode)}]}
                ]

            payload = {media_type_key: [show_item]}

        kodilog("Payload: %s" % payload)

        response = self.call_trakt(
            "sync/history",
            data=payload,
            with_auth=True,
            pagination=False,
        )

        if (
            "added" in response
            and response["added"].get("movies", 0) == 0
            and response["added"].get("episodes", 0) == 0
        ):
            notification("Failed to mark as watched", time=3000)
        else:
            notification("Marked as watched", time=3000)

        return response

    def mark_as_unwatched(self, media_type, season, episode, ids):
        if media_type in ("movie", "movies"):
            media_type_key = "movies"
        else:
            media_type_key = "shows"

        payload = {media_type_key: [{"ids": {"tmdb": int(ids["tmdb"])}}]}
        return self.call_trakt(
            "sync/history/remove",
            data=payload,
            with_auth=True,
            pagination=False,
        )

    def trakt_fetch_sorted_list(self, list_type, media_type, sort_type=None, limit=20):
        data = self.trakt_fetch_watchlist(list_type, media_type)

        if sort_type == "recent":
            data.sort(key=lambda k: k["collected_at"], reverse=True)
        elif sort_type == "random":
            random.shuffle(data)
        elif sort_type is None and list_type == "watchlist":
            sort_order = trakt_lists_sort_order("watchlist")
            if sort_order == 0:
                data = sort_for_article(data, "title")
            elif sort_order == 1:
                data.sort(key=lambda k: k["collected_at"], reverse=True)
            else:
                data.sort(key=lambda k: k.get("released"), reverse=True)

        return data[:limit]

    def trakt_fetch_watchlist(self, list_type, media_type):
        def _process(params):
            raw_data = self.get_trakt(params)
            return [
                {
                    "media_ids": {
                        "tmdb": item[media_key]["ids"].get("tmdb", ""),
                        "imdb": item[media_key]["ids"].get("imdb", ""),
                        "tvdb": item[media_key]["ids"].get("tvdb", ""),
                    },
                    "title": item[media_key]["title"],
                    "collected_at": item.get(collected_at_key),
                    "released": item[media_key].get(
                        release_date_key, default_release_date
                    ),
                }
                for item in raw_data
            ]

        if media_type in ("movie", "movies"):
            media_key = "movie"
            release_date_key = "released"
            collected_at_key = "listed_at"
            default_release_date = "2050-01-01"
        else:
            media_key = "show"
            release_date_key = "first_aired"
            collected_at_key = "listed_at"
            default_release_date = self.standby_date

        api_path = "sync/%s/%s?extended=full"

        params = {
            "path": api_path,
            "path_insert": (list_type, media_key),
            "with_auth": True,
            "pagination": False,
        }

        return _process(params)

    def trakt_search_lists(self, search_title, page_no):
        def _process(dummy_arg):
            return self.call_trakt(
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

    def trakt_favorites(self, media_type):
        def _process(params):
            return [
                {
                    "media_ids": {
                        "tmdb": i[i["type"]]["ids"].get("tmdb", ""),
                        "imdb": i[i["type"]]["ids"].get("imdb", ""),
                        "tvdb": i[i["type"]]["ids"].get("tvdb", ""),
                    }
                }
                for i in self.get_trakt(params)
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

    def get_trakt_list_contents(self, list_type, user, slug, with_auth):
        def _process(params):
            return [
                {
                    "media_ids": i[i["type"]]["ids"],
                    "title": i[i["type"]]["title"],
                    "type": i["type"],
                    "order": c,
                }
                for c, i in enumerate(self.get_trakt(params))
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

    def trakt_trending_popular_lists(self, list_type, page_no):
        string = "trakt_%s_user_lists_%s" % (list_type, page_no)
        params = {
            "path": "lists/%s",
            "path_insert": list_type,
            "params": {"limit": 50},
            "page_no": page_no,
        }
        return cache_object(self.get_trakt, string, params, False)

    def trakt_get_lists(self, list_type):
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
        return cache_trakt_object(self.get_trakt, string, params)

    def make_trakt_slug(self, name):
        import re

        name = name.strip()
        name = name.lower()
        name = re.sub("[^a-z0-9_]", "-", name)
        name = re.sub("--+", "-", name)
        return name


class TraktScrobble(TraktBase):
    def trakt_start_scrobble(self, data):
        kodilog("Starting scrobble")
        payload = {"progress": 0}
        if data["mode"] == "movies":
            payload["movie"] = {"ids": {"tmdb": data["ids"]["tmdb_id"]}}
        elif data["mode"] == "tv":
            if data.get("tv_data") is None:
                return
            payload["show"] = {"ids": {"tmdb": data["ids"]["tmdb_id"]}}
            payload["episode"] = {
                "season": data.get("tv_data").get("season"),
                "number": data.get("tv_data").get("episode"),
            }

        kodilog("Scrobble payload: %s" % payload)
        self.call_trakt("scrobble/start", data=payload, with_auth=True)

    def trakt_pause_scrobble(self, data):
        payload = {"progress": 0}
        if data["mode"] == "movies":
            payload["movie"] = {"ids": {"tmdb": data["ids"]["tmdb_id"]}}
        elif data["mode"] == "tv":
            payload["show"] = {"ids": {"tmdb": data["ids"]["tmdb_id"]}}
            payload["episode"] = {
                "season": data.get("tv_data").get("season"),
                "number": data.get("tv_data").get("episode"),
            }

        self.call_trakt("scrobble/pause", data=payload, with_auth=True)

    def trakt_stop_scrobble(self, data):
        kodilog("Stopping scrobble")

        progress = data["progress"]
        payload = {
            "progress": progress,
        }
        if data["mode"] == "movies":
            payload["movie"] = {"ids": {"tmdb": data["ids"]["tmdb_id"]}}
        elif data["mode"] == "tv":
            payload["show"] = {"ids": {"tmdb": data["ids"]["tmdb_id"]}}
            payload["episode"] = {
                "season": data.get("tv_data").get("season"),
                "number": data.get("tv_data").get("episode"),
            }

        self.call_trakt("scrobble/stop", data=payload, with_auth=True)

    def trakt_get_last_tracked_position(self, data):
        try:
            kodilog("Fetching last tracked position")
            media_type = "movies" if data["mode"] == "movies" else "shows"
            season = data.get("tv_data", {}).get("season")
            tmdb_id = data.get("ids", {}).get("tmdb_id")
            path = f"sync/playback/{media_type}"
            response = self.call_trakt(path, with_auth=True)
            kodilog(f"Response: {response}", level=xbmc.LOGDEBUG)
            for item in response:
                if item["type"] == "movie" and item["movie"]["ids"]["tmdb"] == tmdb_id:
                    return item.get("progress", 0)
                elif item["type"] == "show" and item["episode"]["season"] == season:
                    return item.get("progress", 0)
        except Exception as e:
            kodilog(f"Error fetching last tracked position: {e}")
        return 0


class TraktCache(TraktBase):
    def clear_all_trakt_cache_data(self):
        try:
            dbcon = connect_database("trakt_db")
            for table in ("trakt_data", "progress", "watched", "watched_status"):
                dbcon.execute(BASE_DELETE % table)
            dbcon.execute("VACUUM")
            return True
        except:
            return False

    def clear_cache(self, cache_type):
        success = True
        if cache_type == "trakt":
            success = self.clear_all_trakt_cache_data()
        elif cache_type == "list":
            success = lists_cache.delete_all_lists()
        if success:
            return success


class TraktAPI:
    def __init__(self):
        self.auth = TraktAuthentication()
        self.movies = TraktMovies()
        self.tv = TraktTV()
        self.anime = TraktAnime()
        self.lists = TraktLists()
        self.scrobble = TraktScrobble()
        self.cache = TraktCache()


class ProviderException(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)
        notification(self.message)
