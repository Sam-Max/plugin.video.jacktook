import xbmc
from lib.api.trakt.trakt import TraktAPI
from lib.api.trakt.trakt_cache import trakt_watched_cache
from lib.utils.kodi.utils import kodilog, get_setting

class TraktSyncService:
    def run(self):
        if not get_setting("trakt_enabled") or not get_setting("is_trakt_auth"):
            kodilog("Trakt not enabled or not authenticated, skipping sync.")
            return

        kodilog("Starting Trakt Sync...")
        try:
            api = TraktAPI()
            
            # Sync Movies
            movies = api.movies.get_watched_movies()
            if movies:
                insert_list = []
                for item in movies:
                    # Schema: (db_type, media_id, season, episode, last_played, title)
                    # item structure: {'plays': 1, 'last_watched_at': '...', 'movie': {'ids': {'tmdb': ...}, 'title': ...}}
                    tmdb_id = item['movie']['ids'].get('tmdb')
                    if not tmdb_id:
                        continue
                    title = item['movie']['title']
                    last_watched = item['last_watched_at']
                    insert_list.append(("movie", str(tmdb_id), None, None, last_watched, title))
                
                trakt_watched_cache.set_bulk_movie_watched(insert_list)
                kodilog(f"Synced {len(insert_list)} watched movies from Trakt")

            # Sync Shows
            shows = api.tv.get_watched_shows()
            if shows:
                insert_list = []
                for item in shows:
                    # item structure: {'plays': 1, 'last_watched_at': '...', 'show': {'ids': {'tmdb': ...}, 'title': ...}, 'seasons': [...]}
                    show_tmdb = item['show']['ids'].get('tmdb')
                    if not show_tmdb:
                        continue
                    show_title = item['show']['title']
                    for season in item.get('seasons', []):
                        season_num = season['number']
                        for episode in season.get('episodes', []):
                            episode_num = episode['number']
                            last_watched = episode['last_watched_at']
                            insert_list.append(("episode", str(show_tmdb), season_num, episode_num, last_watched, show_title))
                
                trakt_watched_cache.set_bulk_tvshow_watched(insert_list)
                kodilog(f"Synced {len(insert_list)} watched episodes from Trakt")

            # Sync Playback Progress (Movies)
            paused_movies = api.scrobble.trakt_get_playback_progress("movies")
            if paused_movies:
                insert_list = []
                for item in paused_movies:
                    # item: {progress: 10.0, paused_at: ..., id: ..., type: movie, movie: ...}
                    tmdb_id = item['movie']['ids'].get('tmdb')
                    if not tmdb_id: continue
                    insert_list.append((
                        "movie", str(tmdb_id), None, None,
                        str(item.get('progress', 0)), "0", item.get('paused_at'), item.get('id'), item['movie']['title']
                    ))
                trakt_watched_cache.set_bulk_movie_progress(insert_list)
                kodilog(f"Synced {len(insert_list)} movie progress items from Trakt")

            # Sync Playback Progress (Episodes)
            paused_episodes = api.scrobble.trakt_get_playback_progress("episodes")
            if paused_episodes:
                insert_list = []
                for item in paused_episodes:
                    show_tmdb = item['show']['ids'].get('tmdb')
                    if not show_tmdb: continue
                    insert_list.append((
                        "episode", str(show_tmdb), item['episode']['season'], item['episode']['number'],
                        str(item.get('progress', 0)), "0", item.get('paused_at'), item.get('id'),
                        f"{item['show']['title']} - {item['episode']['title']}"
                    ))
                trakt_watched_cache.set_bulk_tvshow_progress(insert_list)
                kodilog(f"Synced {len(insert_list)} episode progress items from Trakt")
                 
        except Exception as e:
            kodilog(f"Error during Trakt Sync: {e}")
