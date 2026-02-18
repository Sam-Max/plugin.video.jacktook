from lib.utils.kodi.utils import translation, get_setting
from lib.utils.views.continue_watching import has_continue_watching_items


tv_items = [
    {
        "name": translation(90028),
        "mode": "tv",
        "api": "tmdb",
        "query": "tmdb_trending",
        "icon": "tmdb.png",
    },
    {
        "name": translation(90064),
        "mode": "tv",
        "api": "tmdb",
        "query": "tmdb_popular",
        "icon": "tmdb.png",
    },
    {
        "name": translation(90086),
        "mode": "tv",
        "api": "tmdb",
        "query": "tmdb_airing_today",
        "icon": "tmdb.png",
    },
    {
        "name": translation(90025),
        "mode": "tv",
        "api": "tmdb",
        "query": "tmdb_genres",
        "icon": "tmdb.png",
    },
    {
        "name": translation(90026),
        "mode": "tv",
        "api": "tmdb",
        "query": "tmdb_calendar",
        "icon": "tmdb.png",
    },
    {
        "name": translation(90027),
        "mode": "tv",
        "api": "tmdb",
        "query": "tmdb_years",
        "icon": "tmdb.png",
    },
    {
        "name": translation(90065),
        "mode": "tv",
        "api": "tmdb",
        "query": "tmdb_lang",
        "icon": "tmdb.png",
    },
    {
        "name": translation(90066),
        "mode": "tv",
        "api": "tmdb",
        "query": "tmdb_networks",
        "icon": "tmdb.png",
    },
    {
        "name": translation(90078),
        "mode": "tv",
        "submode": "people_menu",
        "api": "tmdb",
        "query": "tmdb_people",
        "icon": "tmdb.png",
    },
    {
        "name": translation(90073),
        "mode": "tv",
        "api": "mdblist",
        "query": "mdblist",
        "icon": "mdblist.png",
    },
    {
        "name": translation(90028),
        "mode": "tv",
        "api": "trakt",
        "query": "trakt_trending",
        "icon": "trakt.png",
    },
    {
        "name": translation(90029),
        "mode": "tv",
        "api": "trakt",
        "query": "trakt_watched",
        "icon": "trakt.png",
    },
    {
        "name": translation(90030),
        "mode": "tv",
        "api": "trakt",
        "query": "trakt_favorited",
        "icon": "trakt.png",
    },
    {
        "name": translation(90031),
        "mode": "tv",
        "api": "trakt",
        "query": "trakt_popular_lists",
        "icon": "trakt.png",
    },
    {
        "name": translation(90032),
        "mode": "tv",
        "api": "trakt",
        "query": "trakt_trending_lists",
        "icon": "trakt.png",
    },
    {
        "name": translation(90033),
        "mode": "tv",
        "api": "trakt",
        "query": "trakt_recommendations",
        "icon": "trakt.png",
    },
    {
        "name": translation(90034),
        "mode": "tv",
        "api": "trakt",
        "query": "trakt_watched_history",
        "icon": "trakt.png",
    },
    {
        "name": translation(90035),
        "mode": "tv",
        "api": "trakt",
        "query": "trakt_watchlist",
        "icon": "trakt.png",
    },
    {
        "name": "Collection",
        "mode": "tv",
        "api": "trakt",
        "query": "trakt_collection",
        "icon": "trakt.png",
    },
    {
        "name": "Calendar",
        "mode": "tv",
        "api": "trakt",
        "query": "trakt_calendar",
        "icon": "trakt.png",
    },
    {
        "name": "Up Next",
        "mode": "tv",
        "api": "trakt",
        "query": "trakt_up_next",
        "icon": "trakt.png",
    },
]


movie_items = [
    {
        "name": translation(90028),
        "mode": "movies",
        "api": "tmdb",
        "query": "tmdb_trending",
        "icon": "tmdb.png",
    },
    {
        "name": translation(90064),
        "mode": "movies",
        "api": "tmdb",
        "query": "tmdb_popular",
        "icon": "tmdb.png",
    },
    {
        "name": translation(90025),
        "mode": "movies",
        "api": "tmdb",
        "query": "tmdb_genres",
        "icon": "tmdb.png",
    },
    {
        "name": translation(90027),
        "mode": "movies",
        "api": "tmdb",
        "query": "tmdb_years",
        "icon": "tmdb.png",
    },
    {
        "name": translation(90065),
        "mode": "movies",
        "api": "tmdb",
        "query": "tmdb_lang",
        "icon": "tmdb.png",
    },
    {
        "name": translation(90067),
        "mode": "movies",
        "api": "tmdb",
        "query": "tmdb_collections",
        "icon": "tmdb.png",
    },
    {
        "name": translation(90078),
        "mode": "movies",
        "submode": "people_menu",
        "api": "tmdb",
        "query": "tmdb_people",
        "icon": "tmdb.png",
    },
    {
        "name": translation(90073),
        "mode": "movies",
        "api": "mdblist",
        "query": "mdblist",
        "icon": "mdblist.png",
    },
    {
        "name": translation(90028),
        "mode": "movies",
        "api": "trakt",
        "query": "trakt_trending",
        "icon": "trakt.png",
    },
    {
        "name": translation(90036),
        "mode": "movies",
        "api": "trakt",
        "query": "trakt_top10",
        "icon": "trakt.png",
    },
    {
        "name": translation(90029),
        "mode": "movies",
        "api": "trakt",
        "query": "trakt_watched",
        "icon": "trakt.png",
    },
    {
        "name": translation(90030),
        "mode": "movies",
        "api": "trakt",
        "query": "trakt_favorited",
        "icon": "trakt.png",
    },
    {
        "name": translation(90031),
        "mode": "tv",
        "api": "trakt",
        "query": "trakt_popular_lists",
        "icon": "trakt.png",
    },
    {
        "name": translation(90032),
        "mode": "tv",
        "api": "trakt",
        "query": "trakt_trending_lists",
        "icon": "trakt.png",
    },
    {
        "name": translation(90033),
        "mode": "movies",
        "api": "trakt",
        "query": "trakt_recommendations",
        "icon": "trakt.png",
    },
    {
        "name": translation(90034),
        "mode": "movies",
        "api": "trakt",
        "query": "trakt_watched_history",
        "icon": "trakt.png",
    },
    {
        "name": translation(90035),
        "mode": "movies",
        "api": "trakt",
        "query": "trakt_watchlist",
        "icon": "trakt.png",
    },
    {
        "name": "Collection",
        "mode": "movies",
        "api": "trakt",
        "query": "trakt_collection",
        "icon": "trakt.png",
    },
]


anime_items = [
    {
        "name": translation(90037),
        "mode": "anime",
        "category": "Anime_Popular",
        "api": "tmdb",
        "icon": "tmdb.png",
    },
    {
        "name": translation(90038),
        "mode": "anime",
        "category": "Anime_Popular_Recent",
        "api": "tmdb",
        "icon": "tmdb.png",
    },
    {
        "name": translation(90039),
        "mode": "anime",
        "category": "Anime_On_The_Air",
        "api": "tmdb",
        "icon": "tmdb.png",
    },
    {
        "name": translation(90042),
        "mode": "anime",
        "category": "Anime_Top_Rated",
        "api": "tmdb",
        "icon": "tmdb.png",
    },
    {
        "name": translation(90040),
        "mode": "anime",
        "category": "Anime_Years",
        "api": "tmdb",
        "icon": "tmdb.png",
    },
    {
        "name": translation(90041),
        "mode": "anime",
        "category": "Anime_Genres",
        "api": "tmdb",
        "icon": "tmdb.png",
    },
    {
        "name": translation(90028),
        "mode": "anime",
        "category": "Anime_Trending",
        "api": "trakt",
        "icon": "trakt.png",
    },
    {
        "name": translation(90154),
        "mode": "anime",
        "category": "Anime_Trending_Recent",
        "api": "trakt",
        "icon": "trakt.png",
    },
    {
        "name": translation(90043),
        "mode": "anime",
        "category": "Anime_Most_Watched",
        "api": "trakt",
        "icon": "trakt.png",
    },
    {
        "name": translation(90030),
        "mode": "anime",
        "category": "Anime_Favorited",
        "api": "trakt",
        "icon": "trakt.png",
    },
]

animation_items = [
    {
        "name": "Cartoons Popular",
        "mode": "cartoon",
        "category": "Cartoons_Popular",
        "api": "tmdb",
        "icon": "tmdb.png",
    },
    {
        "name": "Animation Popular",
        "mode": "animation",
        "category": "Animation_Popular",
        "api": "tmdb",
        "icon": "tmdb.png",
    },
]

root_menu_items = [
    {
        "name": 90006,
        "icon": "search.png",
        "action": "handle_tmdb_search",
        "params": {"mode": "multi", "page": 1},
    },
    {
        "name": 90200,
        "icon": "continue_watching.png",
        "action": "continue_watching_menu",
        "condition": has_continue_watching_items,
    },  # Continue Watching
    {"name": 90007, "icon": "tv.png", "action": "tv_shows_items"},
    {"name": 90008, "icon": "movies.png", "action": "movies_items"},
    {"name": 90009, "icon": "anime.png", "action": "anime_menu"},
    {"name": 90010, "icon": "tv.png", "action": "tv_menu"},
    {"name": 90011, "icon": "search.png", "action": "direct_menu"},
    {"name": 90012, "icon": "magnet2.png", "action": "torrents"},
    {
        "name": 90013,
        "icon": "telegram.png",
        "action": "telegram_menu",
        "condition": lambda: get_setting("show_telegram_menu") == "true",
    },
    {"name": 90014, "icon": "cloud2.png", "action": "cloud"},
    {"name": 90015, "icon": "download2.png", "action": "downloads_menu"},
    {"name": 90016, "icon": "settings.png", "action": "settings"},
    {"name": 90201, "icon": "library.png", "action": "library_menu"},  # Library
]

history_menu_items = [
    {"name": 90019, "icon": "history.png", "action": "files_history"},
    {"name": 90020, "icon": "history.png", "action": "titles_history"},
    {"name": 90021, "icon": "history.png", "action": "titles_calendar"},
]

library_menu_items = [
    {"name": 90202, "icon": "tv.png", "action": "library_shows"},  # My Shows
    {"name": 90203, "icon": "movies.png", "action": "library_movies"},  # My Movies
    {
        "name": 90021,
        "icon": "history.png",
        "action": "library_calendar",
    },  # Upcoming Episodes
]
