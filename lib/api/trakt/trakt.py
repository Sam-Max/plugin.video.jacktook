import json
import datetime
import random
import time
from typing import Any, Dict
import requests
from lib.utils.general.utils import set_pluging_category
import xbmc

from lib.api.trakt.lists_cache import lists_cache
from lib.api.trakt.base_cache import BASE_DELETE, connect_database
from lib.api.trakt.lists_cache import lists_cache_object
from lib.api.trakt.main_cache import cache_object
from lib.api.trakt.main_cache import cache_object
from lib.api.trakt.trakt_cache import (
    cache_trakt_object,
    clear_trakt_collection_watchlist_data,
    clear_trakt_favorites,
    clear_trakt_list_contents_data,
    clear_trakt_list_data,
    trakt_watched_cache,
)
from lib.api.trakt.trakt_utils import clean_ids, sort_for_article, sort_list
from lib.gui.qr_progress_dialog import QRProgressDialog
from lib.jacktook.utils import ADDON_PATH
from lib.utils.debrid.qrcode_utils import make_qrcode
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
    translation,
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
        notification(translation(90382))
        return None

    def no_secret_key(self):
        notification(translation(90383))
        return None

    def _handle_unauthorized(self):
        kodilog("Trakt unauthorized - Revoking authentication")
        set_property("trakt_token", "")
        set_property("trakt_refresh", "")
        set_property("trakt_expires", "")
        set_setting("trakt_user", EMPTY_USER)
        set_setting("is_trakt_auth", "false")
        notification(translation(90408), time=5000)
        try:
            TraktCache().clear_all_trakt_cache_data()
        except:
            pass

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

            if token:
                headers["Authorization"] = f"Bearer {token}"

        if pagination:
            params["page"] = page_no

        response = self._send_request(path, params, data, headers, is_delete, method)

        # Rate Limiting Handling
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 1))
            kodilog(f"Trakt Rate Limit Exceeded. Retrying in {retry_after} seconds.")
            sleep(retry_after * 1000)
            response = self._send_request(
                path, params, data, headers, is_delete, method
            )

        kodilog("Trakt response status code: %s" % response.status_code)
        try:
            response.raise_for_status()
        except requests.HTTPError as error:
            status_code = response.status_code
            if status_code == 401:
                self._handle_unauthorized()
                return []

            status_code = response.status_code
            error_messages = {
                400: "Bad Request",
                401: "Unauthorized",
                403: "Forbidden",
                404: "Not Found",
                422: "Unprocessable Entity",
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
            return requests.post(url, json=data, headers=headers, timeout=self.timeout)
        elif method == "delete":
            return requests.delete(url, json=data, headers=headers, timeout=self.timeout)
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
            path_insert = params.get("path_insert")
            if path_insert is not None:
                if not isinstance(path_insert, (tuple)):
                    path_insert = (path_insert,)
                formatted_path = params["path"] % path_insert
            else:
                formatted_path = params["path"]

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
            if result is not None:
                if params.get("pagination", True):
                    if isinstance(result, (list, tuple)) and len(result) > 0:
                        return result[0]
                    return []
                return result
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
        if response and isinstance(response, dict):
            set_property("trakt_token", response["access_token"])
            set_property("trakt_refresh", response["refresh_token"])
            set_property("trakt_expires", str(time.time() + 82800))  # 23 hours

    def get_trakt_id_by_tmdb(self, tmdb_id, media_type="movie"):
        trakt_object = self.get_trakt_object_by_tmdb(tmdb_id, media_type)
        if trakt_object:
            try:
                return trakt_object["ids"]["trakt"]
            except (KeyError, TypeError):
                return None
        return None

    def get_trakt_object_by_tmdb(self, tmdb_id, media_type="movie"):
        params = {
            "path": "search/tmdb/%s",
            "path_insert": tmdb_id,
            "params": {"type": media_type},
            "with_auth": False,
            "pagination": False,
        }
        results = self.get_trakt(params)
        if results and isinstance(results, list) and len(results) > 0:
            try:
                return results[0][media_type]
            except (KeyError, IndexError, TypeError):
                return None
        return None


class TraktAuthentication(TraktBase):
    def __init__(self):
        super().__init__()

    def get_user_settings(self):
        params = {
            "path": "users/settings",
            "path_insert": (),
            "with_auth": True,
            "pagination": False,
        }
        return self.get_trakt(params)

    def get_account_stats(self):
        params = {
            "path": "users/me/stats",
            "with_auth": True,
            "pagination": False,
        }
        return self.get_trakt(params)

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
        verification_url = str(device_codes["verification_url"])

        # Generate QR code for the verification URL
        qr_code = make_qrcode(verification_url)
        try:
            copy2clip(user_code)
        except:
            pass

        # Create and display QR code dialog
        progressDialog = QRProgressDialog("qr_dialog.xml", ADDON_PATH)
        progressDialog.setup(
            translation(90563),
            qr_code,
            verification_url,
            user_code,
            "",
            is_debrid=False,
        )
        progressDialog.show_dialog()

        try:
            time_passed = 0
            while not progressDialog.iscanceled and time_passed < expires_in:
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
                    progressDialog.update_progress(100, translation(90545))
                    break
                elif status_code == 400:
                    time_passed = time.time() - start
                    progress = int(100 * time_passed / expires_in)
                    progressDialog.update_progress(progress)
                else:
                    break
        except:
            pass
        try:
            progressDialog.close_dialog()
        except:
            pass
        return result

    def trakt_authenticate(self):
        code = self.trakt_get_device_code()
        token = self.trakt_get_device_token(code)
        if not token:
            kodilog("Trakt authentication failed, no token received")
            notification(translation(90384), time=3000)
            return False
        set_property("trakt_token", str(token["access_token"]))
        set_property("trakt_refresh", str(token["refresh_token"]))
        set_property("trakt_expires", str(time.time() + 82800))  # 23 hours
        try:
            user = self.call_trakt("users/me")
            if user and isinstance(user, dict):
                set_setting("trakt_user", str(user["username"]))
                set_setting("is_trakt_auth", "true")
                notification(translation(90385), time=3000)
                return True
        except:
            kodilog("Trakt user not found, setting to empty user")
            set_setting("is_trakt_auth", "false")
            notification(translation(90384), time=3000)
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
        notification(translation(90386), time=3000)


class TraktMovies(TraktBase):
    def trakt_movies_trending(self, page_no):
        set_pluging_category(translation(90028))
        string = "trakt_movies_trending_%s" % page_no
        params = {
            "path": "movies/trending",
            "params": {"limit": 20},
            "page_no": page_no,
        }
        return lists_cache_object(self.get_trakt, string, params)

    def trakt_movies_trending_recent(self, page_no):
        set_pluging_category(translation(90024))
        current_year = get_datetime().year
        years = "%s-%s" % (str(current_year - 1), str(current_year))
        string = "trakt_movies_trending_recent_%s" % page_no
        params = {
            "path": "movies/trending",
            "params": {"limit": 20, "years": years},
            "page_no": page_no,
        }
        return lists_cache_object(self.get_trakt, string, params)

    def trakt_movies_top10_boxoffice(self):
        set_pluging_category(translation(90036))
        string = "trakt_movies_top10_boxoffice"
        params = {"path": "movies/boxoffice", "pagination": False}
        return lists_cache_object(self.get_trakt, string, params)

    def trakt_movies_most_watched(self, page_no):
        set_pluging_category(translation(90029))
        string = "trakt_movies_most_watched_%s" % page_no
        params = {
            "path": "movies/watched/daily",
            "params": {"limit": 20},
            "page_no": page_no,
        }
        return lists_cache_object(self.get_trakt, string, params)

    def trakt_movies_most_favorited(self, page_no):
        set_pluging_category(translation(90030))
        string = "trakt_movies_most_favorited%s" % page_no
        params = {
            "path": "movies/favorited/daily",
            "params": {"limit": 20},
            "page_no": page_no,
        }
        return lists_cache_object(self.get_trakt, string, params)

    def trakt_recommendations(self, media_type):
        set_pluging_category(translation(90033))
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

    def get_watched_movies(self):
        params = {
            "path": "sync/watched/movies",
            "with_auth": True,
            "pagination": False,
            "params": {"extended": "full"},
        }
        return self.get_trakt(params)

    def trakt_movies_progress(self):
        set_pluging_category(translation(90200))
        try:
            return TraktScrobble().trakt_get_playback_progress("movies")
        except Exception:
            return []

    def trakt_collection(self, page_no):
        set_pluging_category(translation(90294))
        params = {
            "path": "sync/collection/movies",
            "params": {"limit": 20, "extended": "full"},
            "page_no": page_no,
            "with_auth": True,
        }
        return self.get_trakt(params)


class TraktTV(TraktBase):
    def trakt_tv_trending(self, page_no):
        set_pluging_category(translation(90028))
        string = "trakt_tv_trending_%s" % page_no
        params = {
            "path": "shows/trending",
            "params": {"limit": 20},
            "page_no": page_no,
        }
        return lists_cache_object(self.get_trakt, string, params)

    def trakt_tv_trending_recent(self, page_no):
        set_pluging_category(translation(90024))
        current_year = get_datetime().year
        years = "%s-%s" % (str(current_year - 1), str(current_year))
        string = "trakt_tv_trending_recent_%s" % page_no
        params = {
            "path": "shows/trending",
            "params": {"limit": 20, "years": years},
            "page_no": page_no,
        }
        return lists_cache_object(self.get_trakt, string, params)

    def trakt_tv_most_watched(self, page_no):
        set_pluging_category(translation(90029))
        string = "trakt_tv_most_watched_%s" % page_no
        params = {
            "path": "shows/watched/daily",
            "params": {"limit": 20},
            "page_no": page_no,
        }
        return lists_cache_object(self.get_trakt, string, params)

    def trakt_tv_most_favorited(self, page_no):
        set_pluging_category(translation(90030))
        string = "trakt_tv_most_favorited_%s" % page_no
        params = {
            "path": "shows/favorited/daily",
            "params": {"limit": 20},
            "page_no": page_no,
        }
        return lists_cache_object(self.get_trakt, string, params)

    def trakt_recommendations(self, media_type):
        set_pluging_category(translation(90033))
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

    def get_watched_shows(self):
        params = {
            "path": "sync/watched/shows",
            "with_auth": True,
            "pagination": False,
            "params": {"extended": "full"},
        }
        return self.get_trakt(params)

    @staticmethod
    def _parse_iso_date(value):
        if not value:
            return None
        try:
            return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return None

    @staticmethod
    def _is_episode_aired(air_date, now_dt):
        if not air_date:
            return True
        now_date = now_dt.date() if hasattr(now_dt, "date") else now_dt
        try:
            return datetime.datetime.strptime(air_date, "%Y-%m-%d").date() <= now_date
        except ValueError:
            return True

    @staticmethod
    def _last_watched_episode(show_item):
        last_episode = None
        last_timestamp = None

        for season in show_item.get("seasons", []):
            season_number = season.get("number")
            if not season_number or season_number == 0:
                continue

            for episode in season.get("episodes", []):
                episode_number = episode.get("number")
                if not episode_number:
                    continue

                episode_key = (int(season_number), int(episode_number))
                watched_at = episode.get("last_watched_at") or show_item.get(
                    "last_watched_at"
                )
                watched_dt = TraktTV._parse_iso_date(watched_at)

                if watched_dt:
                    if last_timestamp is None or watched_dt > last_timestamp:
                        last_timestamp = watched_dt
                        last_episode = episode_key
                elif last_episode is None or episode_key > last_episode:
                    last_episode = episode_key

        return last_episode, last_timestamp

    @staticmethod
    def _find_next_episode(fetcher, tmdb_id, starting_point, now_dt):
        if not tmdb_id or not starting_point:
            return None

        show_details = fetcher("tv_details", tmdb_id)
        total_seasons = getattr(show_details, "number_of_seasons", 0) or 0
        start_season, start_episode = starting_point

        for season_number in range(max(1, int(start_season)), int(total_seasons) + 1):
            season_details = fetcher(
                "season_details", {"id": tmdb_id, "season": season_number}
            )
            episodes = getattr(season_details, "episodes", []) or []
            for episode in episodes:
                episode_number = getattr(episode, "episode_number", 0) or 0
                if season_number == int(start_season) and episode_number <= int(
                    start_episode
                ):
                    continue

                air_date = getattr(episode, "air_date", None)
                if not TraktTV._is_episode_aired(air_date, now_dt):
                    continue

                return {
                    "season": season_number,
                    "number": episode_number,
                    "title": getattr(episode, "name", ""),
                    "first_aired": air_date,
                }

        return None

    @classmethod
    def _build_up_next_entries(cls, watched_shows, progress_items, fetcher=None, now_dt=None, hidden_items=None):
        if fetcher is None:
            from lib.clients.tmdb.utils.utils import tmdb_get as fetcher

        now_dt = now_dt or get_datetime(string=False)
        entries = []
        progress_by_show = {}
        hidden_items = hidden_items or []

        for item in progress_items or []:
            show = item.get("show", {})
            ids = show.get("ids", {})
            tmdb_id = ids.get("tmdb")
            episode = item.get("episode", {})
            if not tmdb_id or int(tmdb_id) in hidden_items or not episode:
                continue

            season_number = episode.get("season")
            episode_number = episode.get("number")
            if not season_number or int(season_number) == 0 or not episode_number:
                continue
            if not cls._is_episode_aired(episode.get("first_aired"), now_dt):
                continue

            progress_entry = {
                "type": "resume",
                "show": show,
                "episode": {
                    "season": season_number,
                    "number": episode_number,
                    "title": episode.get("title", ""),
                    "first_aired": episode.get("first_aired"),
                },
                "progress": item.get("progress", 0),
                "activity_at": item.get("paused_at") or "",
            }

            existing_entry = progress_by_show.get(int(tmdb_id))
            if existing_entry:
                existing_activity = existing_entry.get("activity_at", "")
                new_activity = progress_entry.get("activity_at", "")
                if (new_activity, progress_entry.get("progress", 0)) <= (
                    existing_activity,
                    existing_entry.get("progress", 0),
                ):
                    continue

            progress_by_show[int(tmdb_id)] = progress_entry

        entries.extend(progress_by_show.values())

        for show_item in watched_shows or []:
            show = show_item.get("show", {})
            ids = show.get("ids", {})
            tmdb_id = ids.get("tmdb")
            if not tmdb_id:
                continue

            tmdb_id = int(tmdb_id)
            if tmdb_id in progress_by_show or tmdb_id in hidden_items:
                continue

            last_episode, last_timestamp = cls._last_watched_episode(show_item)
            if not last_episode:
                continue

            next_episode = cls._find_next_episode(fetcher, tmdb_id, last_episode, now_dt)
            if not next_episode:
                continue

            entries.append(
                {
                    "type": "next",
                    "show": show,
                    "episode": next_episode,
                    "progress": 0,
                    "activity_at": last_timestamp.isoformat() if last_timestamp else "",
                }
            )

        return sorted(
            entries,
            key=lambda item: (
                1 if item.get("type") == "resume" else 0,
                item.get("activity_at", ""),
                item.get("progress", 0),
            ),
            reverse=True,
        )

    def trakt_get_hidden_items(self, section="progress_watched"):
        def _process(params):
            result = self.get_trakt(params)
            hidden = []
            if result:
                for item in result:
                    if item.get("type") == "show":
                        tmdb_id = item.get("show", {}).get("ids", {}).get("tmdb")
                        if tmdb_id:
                            hidden.append(int(tmdb_id))
            return hidden

        string = "trakt_hidden_items_%s" % section
        params = {
            "path": "users/hidden/%s" % section,
            "params": {"limit": 1000},
            "with_auth": True,
            "pagination": False,
        }
        return cache_trakt_object(_process, string, params)

    def trakt_up_next(self):
        watched_shows = self.get_watched_shows()
        progress_items = TraktScrobble().trakt_get_playback_progress("episodes")
        hidden_items = self.trakt_get_hidden_items("progress_watched")
        return self._build_up_next_entries(watched_shows, progress_items, hidden_items=hidden_items)

    def trakt_collection(self, page_no):
        set_pluging_category(translation(90294))
        params = {
            "path": "sync/collection/shows",
            "params": {"limit": 20, "extended": "full"},
            "page_no": page_no,
            "with_auth": True,
        }
        return self.get_trakt(params)


class TraktAnime(TraktBase):
    def _get_path_prefix(self, mode):
        return "movies" if mode == "movies" else "shows"

    def trakt_anime_trending(self, page_no, mode="tv"):
        path_prefix = self._get_path_prefix(mode)
        string = "trakt_anime_trending_%s_%s" % (mode, page_no)
        params = {
            "path": "%s/trending" % path_prefix,
            "params": {"genres": "anime", "limit": 20},
            "page_no": page_no,
        }
        return lists_cache_object(self.get_trakt, string, params)

    def trakt_anime_trending_recent(self, page_no, mode="tv"):
        path_prefix = self._get_path_prefix(mode)
        current_year = get_datetime().year
        years = "%s-%s" % (str(current_year - 1), str(current_year))
        string = "trakt_anime_trending_recent_%s_%s" % (mode, page_no)
        params = {
            "path": "%s/trending" % path_prefix,
            "params": {"genres": "anime", "limit": 20, "years": years},
            "page_no": page_no,
        }
        return lists_cache_object(self.get_trakt, string, params)

    def trakt_anime_most_watched(self, page_no, mode="tv"):
        path_prefix = self._get_path_prefix(mode)
        string = "trakt_anime_most_watched_%s_%s" % (mode, page_no)
        params = {
            "path": "%s/watched/daily" % path_prefix,
            "params": {"genres": "anime", "limit": 20},
            "page_no": page_no,
        }
        return lists_cache_object(self.get_trakt, string, params)

    def trakt_anime_most_favorited(self, page_no, mode="tv"):
        path_prefix = self._get_path_prefix(mode)
        string = "trakt_anime_most_favorited_%s_%s" % (mode, page_no)
        params = {
            "path": "%s/favorited/daily" % path_prefix,
            "params": {"genres": "anime", "limit": 20},
            "page_no": page_no,
        }
        return lists_cache_object(self.get_trakt, string, params)


class TraktLists(TraktBase):
    @staticmethod
    def _history_payload(media_type, season, episode, ids):
        if media_type in ("movie", "movies"):
            media_type_key = "movies"
            payload = {media_type_key: [{"ids": {"tmdb": int(ids["tmdb"])}}]}
        else:
            media_type_key = "shows"

            show_item: Dict[str, Any] = {"ids": {"tmdb": int(ids["tmdb"])}}

            if season:
                show_item["seasons"] = [{"number": int(season)}]

            if season and episode:
                show_item["seasons"] = [
                    {"number": int(season), "episodes": [{"number": int(episode)}]}
                ]

            payload = {media_type_key: [show_item]}

        return payload

    @staticmethod
    def _ids_match(candidate_ids, target_ids):
        for key in ("trakt", "tmdb", "tvdb", "imdb"):
            candidate = candidate_ids.get(key)
            target = target_ids.get(key) or target_ids.get(f"{key}_id")
            if candidate and target and str(candidate) == str(target):
                return True
        return False

    def get_collection_items(self, media_type):
        if media_type in ("movie", "movies"):
            path = "sync/collection/movies"
        else:
            path = "sync/collection/shows"
        return self.get_trakt(
            {
                "path": path,
                "with_auth": True,
                "pagination": False,
                "params": {"extended": "full"},
            }
        )

    def build_collection_remove_payload(self, media_type, ids):
        if media_type in ("movie", "movies"):
            return self._list_item_payload(media_type, ids)

        items = self.get_collection_items(media_type)
        if not items:
            return None

        for item in items:
            show = item.get("show") or item
            show_ids = show.get("ids", {})
            if not self._ids_match(show_ids, ids):
                continue

            payload = {"shows": [{"ids": clean_ids(show_ids)}]}
            if show.get("title"):
                payload["shows"][0]["title"] = show.get("title")
            if show.get("year"):
                payload["shows"][0]["year"] = show.get("year")

            seasons = item.get("seasons", []) or []
            if seasons:
                payload["shows"][0]["seasons"] = []
                for season in seasons:
                    season_number = season.get("number")
                    if not season_number:
                        continue
                    season_payload = {"number": int(season_number)}
                    episodes = season.get("episodes", []) or []
                    if episodes:
                        season_payload["episodes"] = []
                        for episode in episodes:
                            episode_number = episode.get("number")
                            if episode_number:
                                season_payload["episodes"].append(
                                    {"number": int(episode_number)}
                                )
                    payload["shows"][0]["seasons"].append(season_payload)
            return payload

        return None

    def trakt_watchlist(self, media_type):
        kodilog("Fetching trakt watchlist")
        result = self.trakt_fetch_sorted_list("watchlist", media_type)
        kodilog("Watchlist result: %s" % result, level=xbmc.LOGDEBUG)
        return result

    def add_to_watchlist(self, media_type, ids):
        original_media_type = media_type
        if media_type in ("movie", "movies"):
            media_type = "movies"
        else:
            media_type = "shows"

        payload = self._list_item_payload(media_type, ids)

        result = self.call_trakt(
            "sync/watchlist",
            data=payload,
            with_auth=True,
            pagination=False,
        )
        lists_cache.delete_prefix("trakt_%s_watchlist_" % ("movies" if media_type == "movies" else "tv"))
        clear_trakt_collection_watchlist_data("watchlist", original_media_type)
        return result

    def remove_from_watchlist(self, media_type, ids):
        original_media_type = media_type
        if media_type in ("movie", "movies"):
            media_type = "movies"
        else:
            media_type = "shows"

        payload = self._list_item_payload(media_type, ids)
        result = self.call_trakt(
            "sync/watchlist/remove",
            data=payload,
            with_auth=True,
            pagination=False,
        )
        lists_cache.delete_prefix("trakt_%s_watchlist_" % ("movies" if media_type == "movies" else "tv"))
        clear_trakt_collection_watchlist_data("watchlist", original_media_type)
        return result

    def trakt_comments(self, media_type, tmdb_id, sort_type="likes", page_no=1):
        if media_type in ("movie", "movies"):
            media_type = "movies"
        else:
            media_type = "shows"

        trakt_id = self.get_trakt_id_by_tmdb(tmdb_id, media_type=media_type[:-1])
        if not trakt_id:
            return []

        params = {
            "path": f"{media_type}/%s/comments/%s",
            "path_insert": (trakt_id, sort_type),
            "with_auth": False,
            "params": {"limit": 20},
            "pagination": True,
            "page_no": page_no,
        }
        return self.get_trakt(params)

    def add_to_collection(self, media_type, ids, payload=None):
        original_media_type = media_type
        if media_type in ("movie", "movies"):
            media_type = "movies"
        else:
            media_type = "shows"

        payload = payload or self._list_item_payload(media_type, ids)

        result = self.call_trakt(
            "sync/collection",
            data=payload,
            with_auth=True,
            pagination=False,
        )
        lists_cache.delete_prefix("trakt_%s_collection_" % ("movies" if media_type == "movies" else "tv"))
        clear_trakt_collection_watchlist_data("collection", original_media_type)
        return result

    def remove_from_collection(self, media_type, ids, payload=None):
        original_media_type = media_type
        if media_type in ("movie", "movies"):
            media_type = "movies"
        else:
            media_type = "shows"

        payload = payload or self._list_item_payload(media_type, ids)
        result = self.call_trakt(
            "sync/collection/remove",
            data=payload,
            with_auth=True,
            pagination=False,
        )
        lists_cache.delete_prefix("trakt_%s_collection_" % ("movies" if media_type == "movies" else "tv"))
        clear_trakt_collection_watchlist_data("collection", original_media_type)
        return result

    def trakt_watched_history(self, media_type, page_no, sort_type="recent"):
        def _process(params, media_type):
            response = self.get_trakt(params)
            history = []
            if not response or not isinstance(response, (list, tuple)):
                return history
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
        payload = self._history_payload(media_type, season, episode, ids)

        kodilog("Payload: %s" % payload)

        response = self.call_trakt(
            "sync/history",
            data=payload,
            with_auth=True,
            pagination=False,
        )

        if (
            response
            and isinstance(response, dict)
            and "added" in response
            and response["added"].get("movies", 0) == 0
            and response["added"].get("episodes", 0) == 0
        ):
            notification(translation(90387), time=3000)
        else:
            notification(translation(90388), time=3000)

        return response

    def mark_as_unwatched(self, media_type, season, episode, ids):
        payload = self._history_payload(media_type, season, episode, ids)
        return self.call_trakt(
            "sync/history/remove",
            data=payload,
            with_auth=True,
            pagination=False,
        )

    def trakt_fetch_sorted_list(self, list_type, media_type, sort_type=None, limit=None):
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
                data.sort(key=lambda k: k["released"], reverse=True)

        return data[:limit] if limit else data

    def trakt_fetch_watchlist(self, list_type, media_type):
        def _process(params):
            raw_data = self.get_trakt(params)
            if not raw_data:
                return []
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
            result = self.call_trakt(
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
            if isinstance(result, tuple):
                result = result[0]
            if not result:
                return []

            normalized = []
            for item in result:
                list_data = item.get("list", {})
                user_data = list_data.get("user", {}) or item.get("user", {}) or {}
                ids = list_data.get("ids", {})
                user_ids = user_data.get("ids", {})
                user_slug = (
                    user_ids.get("slug")
                    or user_data.get("username")
                    or list_data.get("username")
                    or ""
                )
                normalized.append(
                    {
                        "list_type": "search_lists",
                        "name": list_data.get("name", ""),
                        "description": list_data.get("description", ""),
                        "slug": ids.get("slug", ""),
                        "trakt_id": ids.get("trakt"),
                        "user_slug": user_slug,
                        "username": user_data.get("username", ""),
                        "item_count": list_data.get("item_count", 0),
                        "privacy": list_data.get("privacy", "public"),
                        "with_auth": False,
                        "can_like": True,
                    }
                )

            return normalized

        string = "trakt_search_lists_%s_%s" % (search_title, page_no)
        return cache_object(_process, string, "dummy_arg", False, 4)

    def trakt_favorites(self, media_type):
        def _process(params):
            result = self.get_trakt(params)
            if not result:
                return []
            return [
                {
                    "media_ids": {
                        "tmdb": i[i["type"]]["ids"].get("tmdb", ""),
                        "imdb": i[i["type"]]["ids"].get("imdb", ""),
                        "tvdb": i[i["type"]]["ids"].get("tvdb", ""),
                    },
                    "title": i[i["type"]].get("title", ""),
                    "type": i["type"],
                }
                for i in result
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

    def get_trakt_list_contents(self, list_type, user, slug, with_auth, trakt_id=None):
        def _process(params):
            result = self.get_trakt(params)
            if not result:
                return []
            return [
                {
                    "media_ids": i[i["type"]]["ids"],
                    "title": i[i["type"]]["title"],
                    "type": i["type"],
                    "order": c,
                }
                for c, i in enumerate(result)
                if i["type"] in ("movie", "show")
            ]

        string = "trakt_list_contents_%s_%s_%s_%s" % (list_type, user, slug, trakt_id)
        if list_type == "my_lists" and trakt_id:
            params = {
                "path": "users/me/lists/%s/items",
                "path_insert": trakt_id,
                "params": {"extended": "full"},
                "with_auth": True,
                "method": "sort_by_headers",
            }
        elif trakt_id:
            params = {
                "path": "lists/%s/items",
                "path_insert": trakt_id,
                "params": {"extended": "full"},
                "with_auth": with_auth,
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
        set_pluging_category(translation(90072))
        string = "trakt_%s_user_lists_%s" % (list_type, page_no)
        params = {
            "path": "lists/%s",
            "path_insert": list_type,
            "params": {"limit": 50},
            "page_no": page_no,
        }
        return cache_object(self.get_trakt, string, params, False)

    def trakt_get_lists(self, list_type):
        def _process(params):
            result = self.get_trakt(params)
            if not result:
                return []

            normalized = []
            for item in result:
                list_data = item.get("list", item)
                user_data = list_data.get("user", {})
                ids = list_data.get("ids", {})
                user_ids = user_data.get("ids", {})
                user_slug = user_ids.get("slug") or user_data.get("username") or ""
                normalized.append(
                    {
                        "list_type": list_type,
                        "name": list_data.get("name", ""),
                        "description": list_data.get("description", ""),
                        "slug": ids.get("slug", ""),
                        "trakt_id": ids.get("trakt"),
                        "user_slug": user_slug,
                        "username": user_data.get("username", ""),
                        "item_count": list_data.get("item_count", 0),
                        "privacy": list_data.get("privacy", "public"),
                        "with_auth": True,
                        "can_delete": list_type == "my_lists",
                        "can_unlike": list_type == "liked_lists",
                    }
                )

            return normalized

        if list_type == "my_lists":
            string = "trakt_my_lists"
            path = "users/me/lists"
        elif list_type == "liked_lists":
            string = "trakt_liked_lists"
            path = "users/likes/lists"
        else:
            return []

        params = {
            "path": path,
            "params": {"limit": 1000},
            "pagination": False,
            "with_auth": True,
        }
        return cache_trakt_object(_process, string, params)

    def add_to_favorites(self, media_type, ids):
        response = self.call_trakt(
            "sync/favorites",
            data=self._list_item_payload(media_type, ids),
            with_auth=True,
            pagination=False,
        )
        clear_trakt_favorites()
        return response

    def remove_from_favorites(self, media_type, ids):
        response = self.call_trakt(
            "sync/favorites/remove",
            data=self._list_item_payload(media_type, ids),
            with_auth=True,
            pagination=False,
        )
        clear_trakt_favorites()
        return response

    def create_list(self, name, description="", privacy="private"):
        response = self.call_trakt(
            "users/me/lists",
            data={
                "name": name,
                "description": description,
                "privacy": privacy,
                "display_numbers": True,
                "allow_comments": True,
            },
            with_auth=True,
            pagination=False,
        )
        clear_trakt_list_data("my_lists")
        clear_trakt_list_contents_data("my_lists")
        return response

    def delete_list(self, trakt_id):
        response = self.call_trakt(
            "users/me/lists/%s" % trakt_id,
            method="delete",
            with_auth=True,
            pagination=False,
        )
        clear_trakt_list_data("my_lists")
        clear_trakt_list_contents_data("my_lists")
        return response

    def like_list(self, user_slug, trakt_id):
        path = f"users/{user_slug}/lists/{trakt_id}/like" if user_slug else "lists/%s/like" % trakt_id
        response = self.call_trakt(
            path,
            data={},
            with_auth=True,
            pagination=False,
        )
        clear_trakt_list_data("liked_lists")
        return response

    def unlike_list(self, user_slug, trakt_id):
        path = f"users/{user_slug}/lists/{trakt_id}/like" if user_slug else "lists/%s/like" % trakt_id
        response = self.call_trakt(
            path,
            method="delete",
            with_auth=True,
            pagination=False,
        )
        clear_trakt_list_data("liked_lists")
        clear_trakt_list_contents_data("liked_lists")
        return response

    def _list_item_payload(self, media_type, ids):
        media_key = "movies" if media_type in ("movie", "movies") else "shows"
        normalized_ids = clean_ids(
            {
                "tmdb": ids.get("tmdb") or ids.get("tmdb_id"),
                "tvdb": ids.get("tvdb") or ids.get("tvdb_id"),
                "imdb": ids.get("imdb") or ids.get("imdb_id"),
            }
        )
        for key in ("tmdb", "tvdb"):
            if key in normalized_ids:
                try:
                    normalized_ids[key] = int(normalized_ids[key])
                except (TypeError, ValueError):
                    pass

        payload = {
            media_key: [
                {
                    "ids": normalized_ids
                }
            ]
        }
        return payload

    def add_item_to_list(self, trakt_id, media_type, ids):
        response = self.call_trakt(
            "users/me/lists/%s/items" % trakt_id,
            data=self._list_item_payload(media_type, ids),
            with_auth=True,
            pagination=False,
        )
        clear_trakt_list_data("my_lists")
        clear_trakt_list_contents_data("my_lists")
        return response

    def remove_item_from_list(self, trakt_id, media_type, ids):
        response = self.call_trakt(
            "users/me/lists/%s/items/remove" % trakt_id,
            data=self._list_item_payload(media_type, ids),
            with_auth=True,
            pagination=False,
        )
        clear_trakt_list_data("my_lists")
        clear_trakt_list_contents_data("my_lists")
        return response

    def make_trakt_slug(self, name):
        import re

        name = name.strip()
        name = name.lower()
        name = re.sub("[^a-z0-9_]", "-", name)
        name = re.sub("--+", "-", name)
        return name


class TraktScrobble(TraktBase):
    @staticmethod
    def _scrobble_payload(data):
        from lib.utils.kodi.utils import ADDON_VERSION
        from datetime import datetime
        progress = data.get("progress", 0)
        if isinstance(progress, str):
            try:
                progress = float(progress)
            except ValueError:
                progress = 0.0

        payload: Dict[str, Any] = {
            "progress": progress,
            "app_version": ADDON_VERSION,
            "app_date": datetime.now().strftime("%Y-%m-%d")
        }

        if data["mode"] == "movies":
            payload["movie"] = {"ids": {"tmdb": data["ids"]["tmdb_id"]}}
        elif data["mode"] == "tv":
            if data.get("tv_data") is None:
                return None
            payload["show"] = {"ids": {"tmdb": data["ids"]["tmdb_id"]}}
            payload["episode"] = {
                "season": data.get("tv_data").get("season"),
                "number": data.get("tv_data").get("episode"),
            }

        return payload

    def trakt_start_scrobble(self, data):
        payload = self._scrobble_payload(data)
        if payload is None:
            return

        self.call_trakt("scrobble/start", data=payload, with_auth=True)

    def trakt_pause_scrobble(self, data):
        payload = self._scrobble_payload(data)
        if payload is None or payload.get("progress", 0) < 1.0:
            return

        self.call_trakt("scrobble/pause", data=payload, with_auth=True)

    def trakt_stop_scrobble(self, data):
        kodilog("Stopping scrobble")

        payload = self._scrobble_payload(data)
        if payload is None or payload.get("progress", 0) < 1.0:
            return

        self.call_trakt("scrobble/stop", data=payload, with_auth=True)

    def trakt_get_last_tracked_position(self, data):
        try:
            media_type = "movies" if data["mode"] == "movies" else "episodes"
            season = data.get("tv_data", {}).get("season")
            episode = data.get("tv_data", {}).get("episode")
            tmdb_id = data.get("ids", {}).get("tmdb_id")

            # Check local cache first
            if data["mode"] == "movies":
                cached_progress = trakt_watched_cache.get_progress(
                    "movie", str(tmdb_id)
                )
            else:
                cached_progress = trakt_watched_cache.get_progress(
                    "episode", str(tmdb_id), season, episode
                )

            if cached_progress > 0:
                kodilog(f"Trakt: Found cached resume point: {cached_progress}%")
                return cached_progress

            path = f"sync/playback/{media_type}"
            response = self.call_trakt(path, with_auth=True)
            if response:
                for item in response:
                    try:
                        if item["type"] == "movie":
                            trakt_tmdb = int(item["movie"]["ids"]["tmdb"])
                            local_tmdb = int(tmdb_id)
                            if trakt_tmdb == local_tmdb:
                                progress = item.get("progress", 0)
                                kodilog(
                                    f"Trakt: Found cloud resume point for movie: {progress}%"
                                )
                                return progress
                        elif item["type"] == "episode":
                            trakt_tmdb = int(item["show"]["ids"]["tmdb"])
                            local_tmdb = int(tmdb_id)
                            # TV Show comparison logic
                            if (
                                trakt_tmdb == local_tmdb
                                and item["episode"]["season"] == int(season)
                                and item["episode"]["number"] == int(episode)
                            ):
                                progress = item.get("progress", 0)
                                kodilog(
                                    f"Trakt: Found cloud resume point for episode: {progress}%"
                                )
                                return progress
                    except Exception:
                        continue

        except Exception as e:
            kodilog(f"Trakt: Error fetching last tracked position: {e}")
            return 0.0

        return 0.0

    def trakt_get_playback_progress(self, media_type):
        # media_type: "movies" or "episodes"
        try:
            path = f"sync/playback/{media_type}"
            params = {
                "path": path,
                "params": {"limit": 1000},  # Safety limit
                "with_auth": True,
                "pagination": False,
            }
            return self.get_trakt(params)
        except Exception as e:
            kodilog(f"Error fetching playback progress: {e}")
            return []
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


class TraktCalendar(TraktBase):
    def trakt_my_calendar(self, start_date, days):
        params = {
            "path": "calendars/my/shows/%s/%s",
            "path_insert": (start_date, days),
            "with_auth": True,
            "pagination": False,
            "params": {"extended": "full"},
        }
        return self.get_trakt(params)

    def trakt_all_shows_calendar(self, start_date, days):
        params = {
            "path": "calendars/all/shows/%s/%s",
            "path_insert": (start_date, days),
            "with_auth": True,
            "pagination": False,
            "params": {"extended": "full"},
        }
        return self.get_trakt(params)


class TraktSync(TraktBase):
    def get_last_activities(self):
        return self.call_trakt(
            "sync/last_activities",
            with_auth=True,
            pagination=False,
        )


class TraktAPI:
    def __init__(self):
        self.auth = TraktAuthentication()
        self.movies = TraktMovies()
        self.tv = TraktTV()
        self.anime = TraktAnime()
        self.lists = TraktLists()
        self.scrobble = TraktScrobble()
        self.sync = TraktSync()
        self.cache = TraktCache()
        self.calendar = TraktCalendar()


class ProviderException(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)
        notification(self.message)
