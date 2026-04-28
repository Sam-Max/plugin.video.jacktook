"""
Lazy TMDb initialization utility.

Provides a function to ensure the TMDb API key and language are
configured before any TMDB operation. Since TMDb stores configuration
in environment variables, this only needs to be called once per
addon invocation.
"""

from lib.api.tmdbv3api.tmdb import TMDb
from lib.clients.tmdb.utils.utils import LANGUAGES
from lib.utils.kodi.utils import get_setting


def ensure_tmdb_init():
    """Initialize TMDb API key and language from current settings."""
    tmdb = TMDb()
    tmdb.api_key = get_setting("tmdb_api_key", "b70756b7083d9ee60f849d82d94a0d80")
    try:
        language_index = get_setting("language", 18)
        tmdb.language = LANGUAGES[int(language_index)]
    except (IndexError, ValueError):
        tmdb.language = "en-US"
