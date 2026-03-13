import xbmc
from lib.api.trakt.trakt import TraktAPI
from lib.api.trakt.lists_cache import lists_cache
from lib.api.trakt.trakt_cache import (
    clear_trakt_calendar,
    clear_trakt_favorites,
    clear_trakt_hidden_data,
    clear_trakt_list_contents_data,
    clear_trakt_list_data,
    clear_trakt_watchlist,
    reset_activity,
    trakt_watched_cache,
)
from lib.utils.kodi.utils import get_property_no_fallback, kodilog, get_setting


PAUSE_SERVICES_PROP = "jacktook.pause_services"
DEFAULT_SYNC_INTERVAL_MINUTES = 15
WAIT_STEP_SECONDS = 5

class TraktSyncService:
    def __init__(self, api=None, monitor=None):
        self.api = api or TraktAPI()
        self.monitor = monitor or xbmc.Monitor()

    def run(self):
        if not self._is_trakt_available():
            kodilog("Trakt not enabled or not authenticated, skipping sync.")
            return

        kodilog("Starting Trakt Sync service...")

        try:
            self.sync_activities(force=True)
            while not self.monitor.abortRequested():
                if self._wait_for_next_cycle():
                    return
                if not self._is_trakt_available() or self._services_paused():
                    continue
                self.sync_activities()
        except Exception as e:
            kodilog(f"Error during Trakt Sync: {e}")

    def _is_trakt_available(self):
        return get_setting("trakt_enabled") and get_setting("is_trakt_auth")

    def _services_paused(self):
        return get_property_no_fallback(PAUSE_SERVICES_PROP) == "true"

    def _get_sync_interval_seconds(self):
        try:
            interval = int(get_setting("trakt_sync_interval", DEFAULT_SYNC_INTERVAL_MINUTES))
        except (TypeError, ValueError):
            interval = DEFAULT_SYNC_INTERVAL_MINUTES
        return max(interval, 1) * 60

    def _wait_for_next_cycle(self):
        remaining = self._get_sync_interval_seconds()
        while remaining > 0:
            if self.monitor.waitForAbort(min(WAIT_STEP_SECONDS, remaining)):
                return True
            remaining -= WAIT_STEP_SECONDS
        return False

    def sync_activities(self, force=False):
        latest_activities = self.api.sync.get_last_activities()
        if not latest_activities:
            return set()

        previous_activities = reset_activity(latest_activities)
        changes = self._get_changed_buckets(previous_activities, latest_activities)
        if force and not changes:
            changes = {
                "watched_movies",
                "watched_shows",
                "progress_movies",
                "progress_episodes",
            }

        if not changes:
            kodilog("Trakt sync: no remote activity changes detected")
            return changes

        self._apply_activity_changes(changes)
        return changes

    def _activity_changed(self, previous, latest, *path):
        prev_value = previous
        latest_value = latest
        for key in path:
            if not isinstance(prev_value, dict) or not isinstance(latest_value, dict):
                return False
            prev_value = prev_value.get(key)
            latest_value = latest_value.get(key)
        return bool(latest_value) and prev_value != latest_value

    def _get_changed_buckets(self, previous, latest):
        changes = set()

        if self._activity_changed(previous, latest, "movies", "watched_at"):
            changes.add("watched_movies")
        if self._activity_changed(previous, latest, "episodes", "watched_at"):
            changes.add("watched_shows")
        if self._activity_changed(previous, latest, "movies", "paused_at"):
            changes.add("progress_movies")
        if self._activity_changed(previous, latest, "episodes", "paused_at"):
            changes.add("progress_episodes")
        if self._activity_changed(previous, latest, "movies", "collected_at"):
            changes.add("collection_movies")
        if self._activity_changed(previous, latest, "episodes", "collected_at"):
            changes.add("collection_shows")
        if self._activity_changed(previous, latest, "movies", "watchlisted_at"):
            changes.add("watchlist_movies")
        if self._activity_changed(previous, latest, "shows", "watchlisted_at"):
            changes.add("watchlist_shows")
        if self._activity_changed(previous, latest, "movies", "favorited_at"):
            changes.add("favorites_movies")
        if self._activity_changed(previous, latest, "shows", "favorited_at"):
            changes.add("favorites_shows")
        if self._activity_changed(previous, latest, "movies", "recommendations_at"):
            changes.add("recommendations_movies")
        if self._activity_changed(previous, latest, "shows", "recommendations_at"):
            changes.add("recommendations_shows")
        if self._activity_changed(previous, latest, "lists", "liked_at") or self._activity_changed(
            previous, latest, "lists", "updated_at"
        ):
            changes.add("lists")
        if self._activity_changed(previous, latest, "movies", "hidden_at"):
            changes.add("hidden_movies")
        if self._activity_changed(previous, latest, "shows", "hidden_at"):
            changes.add("hidden_shows")

        return changes

    def _apply_activity_changes(self, changes):
        if "watched_movies" in changes:
            self.sync_watched_movies()
        if "watched_shows" in changes:
            self.sync_watched_shows()
        if "progress_movies" in changes:
            self.sync_movie_progress()
        if "progress_episodes" in changes:
            self.sync_episode_progress()

        self.invalidate_cached_buckets(changes)

    def sync_watched_movies(self):
        movies = self.api.movies.get_watched_movies()
        if not movies:
            trakt_watched_cache.set_bulk_movie_watched([])
            return

        insert_list = []
        for item in movies:
            tmdb_id = item["movie"]["ids"].get("tmdb")
            if not tmdb_id:
                continue
            insert_list.append(
                (
                    "movie",
                    str(tmdb_id),
                    None,
                    None,
                    item["last_watched_at"],
                    item["movie"]["title"],
                )
            )

        trakt_watched_cache.set_bulk_movie_watched(insert_list)
        kodilog(f"Synced {len(insert_list)} watched movies from Trakt")

    def sync_watched_shows(self):
        shows = self.api.tv.get_watched_shows()
        if not shows:
            trakt_watched_cache.set_bulk_tvshow_watched([])
            return

        insert_list = []
        for item in shows:
            show_tmdb = item["show"]["ids"].get("tmdb")
            if not show_tmdb:
                continue
            show_title = item["show"]["title"]
            for season in item.get("seasons", []):
                season_num = season["number"]
                for episode in season.get("episodes", []):
                    insert_list.append(
                        (
                            "episode",
                            str(show_tmdb),
                            season_num,
                            episode["number"],
                            episode["last_watched_at"],
                            show_title,
                        )
                    )

        trakt_watched_cache.set_bulk_tvshow_watched(insert_list)
        kodilog(f"Synced {len(insert_list)} watched episodes from Trakt")

    def sync_movie_progress(self):
        paused_movies = self.api.scrobble.trakt_get_playback_progress("movies")
        if not paused_movies:
            trakt_watched_cache.set_bulk_movie_progress([])
            return

        insert_list = []
        for item in paused_movies:
            tmdb_id = item["movie"]["ids"].get("tmdb")
            if not tmdb_id:
                continue
            insert_list.append(
                (
                    "movie",
                    str(tmdb_id),
                    None,
                    None,
                    str(item.get("progress", 0)),
                    "0",
                    item.get("paused_at"),
                    item.get("id"),
                    item["movie"]["title"],
                )
            )

        trakt_watched_cache.set_bulk_movie_progress(insert_list)
        kodilog(f"Synced {len(insert_list)} movie progress items from Trakt")

    def sync_episode_progress(self):
        paused_episodes = self.api.scrobble.trakt_get_playback_progress("episodes")
        if not paused_episodes:
            trakt_watched_cache.set_bulk_tvshow_progress([])
            return

        insert_list = []
        for item in paused_episodes:
            show_tmdb = item["show"]["ids"].get("tmdb")
            if not show_tmdb:
                continue
            insert_list.append(
                (
                    "episode",
                    str(show_tmdb),
                    item["episode"]["season"],
                    item["episode"]["number"],
                    str(item.get("progress", 0)),
                    "0",
                    item.get("paused_at"),
                    item.get("id"),
                    f"{item['show']['title']} - {item['episode']['title']}",
                )
            )

        trakt_watched_cache.set_bulk_tvshow_progress(insert_list)
        kodilog(f"Synced {len(insert_list)} episode progress items from Trakt")

    def invalidate_cached_buckets(self, changes):
        if "collection_movies" in changes:
            lists_cache.delete_prefix("trakt_movies_collection_")
        if "collection_shows" in changes:
            lists_cache.delete_prefix("trakt_tv_collection_")
        if "watchlist_movies" in changes or "watchlist_shows" in changes:
            clear_trakt_watchlist()
            clear_trakt_calendar()
        if "favorites_movies" in changes or "favorites_shows" in changes:
            clear_trakt_favorites()
        if "recommendations_movies" in changes:
            lists_cache.delete_prefix("trakt_recommendations_movies")
        if "recommendations_shows" in changes:
            lists_cache.delete_prefix("trakt_recommendations_shows")
        if "lists" in changes:
            clear_trakt_list_data("my_lists")
            clear_trakt_list_data("liked_lists")
            clear_trakt_list_contents_data("my_lists")
            clear_trakt_list_contents_data("liked_lists")
        if "hidden_movies" in changes:
            clear_trakt_hidden_data("movies")
        if "hidden_shows" in changes:
            clear_trakt_hidden_data("shows")
