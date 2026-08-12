import json
from datetime import timedelta

from lib.db.cached import cache
from lib.utils.kodi.settings import get_setting
from lib.utils.kodi.utils import kodilog

BUILTIN_SOURCE_SETTINGS = [
    ("jackett_enabled", "Jackett"),
    ("prowlarr_enabled", "Prowlarr"),
    ("jacktookburst_enabled", "Burst"),
    ("jackgram_enabled", "Jackgram"),
    ("easynews_enabled", "Easynews"),
    ("stremio_enabled", "Stremio"),
    ("external_scraper_enabled", "External Scraper"),
]

CACHE_KEY = "source_manager_selection"
KNOWN_CACHE_KEY = "source_manager_known_keys"


def parse_source_selection(raw):
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError):
            return None
    else:
        parsed = raw
    if isinstance(parsed, (str, bytes, dict)):
        return None
    try:
        return list(parsed)
    except TypeError:
        return None


def get_enabled_source_keys(settings_getter=get_setting, stremio_addons_getter=None):
    """Return the Manage Sources keys for providers currently enabled in Settings."""
    if stremio_addons_getter is None:
        from lib.clients.stremio.helpers import get_selected_stream_addons

        stremio_addons_getter = get_selected_stream_addons

    cache_keys = []
    for setting_key, display_name in BUILTIN_SOURCE_SETTINGS:
        if not settings_getter(setting_key):
            continue

        if setting_key == "external_scraper_enabled":
            display_name = settings_getter("external_scraper_module_name") or display_name

        if setting_key == "stremio_enabled":
            try:
                cache_keys.extend(f"Stremio:{addon.key()}" for addon in stremio_addons_getter())
            except Exception as e:
                kodilog(f"Error loading Stremio addons: {e}")
            continue

        cache_keys.append(str(display_name))
    return cache_keys


def reconcile_source_selection(
    cache_keys=None,
    cache_backend=cache,
    settings_getter=get_setting,
    stremio_addons_getter=None,
):
    """Auto-select new Settings sources without re-enabling known deselections."""
    if cache_keys is None:
        cache_keys = get_enabled_source_keys(settings_getter, stremio_addons_getter)
    current_selection = parse_source_selection(cache_backend.get(CACHE_KEY))
    known_keys = parse_source_selection(cache_backend.get(KNOWN_CACHE_KEY)) or []

    if current_selection is None:
        current_selection = list(cache_keys)
        known_keys = list(dict.fromkeys(known_keys + cache_keys))
    else:
        newly_enabled = [key for key in cache_keys if key not in known_keys]
        if not newly_enabled:
            return current_selection
        current_selection.extend(newly_enabled)
        known_keys = list(dict.fromkeys(known_keys + cache_keys))

    cache_backend.set(CACHE_KEY, json.dumps(current_selection), expires=timedelta(days=365))
    cache_backend.set(KNOWN_CACHE_KEY, json.dumps(known_keys), expires=timedelta(days=365))
    return current_selection


def persist_source_selection(selected, cache_keys, cache_backend=cache):
    """Save an explicit dialog selection while retaining historical source keys."""
    known_keys = parse_source_selection(cache_backend.get(KNOWN_CACHE_KEY)) or []
    known_keys = list(dict.fromkeys(known_keys + cache_keys))
    cache_backend.set(CACHE_KEY, json.dumps(selected), expires=timedelta(days=365))
    cache_backend.set(KNOWN_CACHE_KEY, json.dumps(known_keys), expires=timedelta(days=365))
