from lib.clients.tmdb.utils.utils import tmdb_get
from threading import Thread
from concurrent.futures import ThreadPoolExecutor
from lib.utils.kodi.utils import kodilog, get_setting
from lib.api.tmdbv3api.tmdb import TMDb


class StartupPreloader:
    def run(self):
        Thread(target=self._preload).start()

    def _preload(self):
        tmdb = TMDb()
        tmdb.api_key = get_setting("tmdb_api_key", "b70756b7083d9ee60f849d82d94a0d80")
        
        # Helper to fetch seasons for a list of shows
        def _deep_preload_tv(results):
            try:
                if not results: 
                    return
                
                # Handle list vs dict (TMDB response structure variants)
                items = []
                if hasattr(results, 'results'):
                    items = results.results
                elif isinstance(results, dict):
                    items = results.get('results', [])
                else:
                    try:
                        items = list(results)
                    except:
                        pass
                        
                if not isinstance(items, list):
                    items = list(items)
                            
                top_items = items[:5]

                for item in top_items:
                    try:
                        tmdb_id = getattr(item, 'id', None) if hasattr(item, 'id') else item.get('id')
                        name = getattr(item, 'name', 'Unknown') if hasattr(item, 'name') else item.get('name', 'Unknown')
                        
                        if not tmdb_id: continue
                        
                        # 1. Fetch Show Details
                        details = tmdb_get("tv_details", tmdb_id)
                        if not details: 
                            continue
                        
                        # 2. Fetch Season 1
                        tmdb_get("season_details", {'id': tmdb_id, 'season': 1})
                        
                        # 3. Fetch Latest Season
                        num_seasons = getattr(details, 'number_of_seasons', 0) if hasattr(details, 'number_of_seasons') else details.get('number_of_seasons', 0)
                        if num_seasons > 1:
                             tmdb_get("season_details", {'id': tmdb_id, 'season': num_seasons})
                    except Exception as e:
                        pass
            except Exception as e:
                import traceback
                kodilog(f"[StartupPreloader] CRASH in _deep_preload_tv: {e}")
                kodilog(traceback.format_exc())

        with ThreadPoolExecutor(max_workers=5) as executor:
            # 1. Fetch main lists in parallel
            executor.submit(tmdb_get, "trending_movie", 1)
            f_trend_tv = executor.submit(tmdb_get, "trending_tv", 1)
            executor.submit(tmdb_get, "popular_movie", 1)
            f_pop_tv = executor.submit(tmdb_get, "popular_shows", 1)
            
            # Get results (this waits for the specific future, but others run in parallel)
            # We treat TV lists specially to trigger deep preload
            trending_tv = f_trend_tv.result()
            popular_tv = f_pop_tv.result()
            
            # Submit deep preload tasks
            # This will run in the same pool, reusing workers as they free up
            if trending_tv: executor.submit(_deep_preload_tv, trending_tv)
            if popular_tv: executor.submit(_deep_preload_tv, popular_tv)
