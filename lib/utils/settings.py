from .kodi_utils import get_setting, get_property, ADDON_ID
import xbmc


def addon_settings():
    return xbmc.executebuiltin(f"Addon.OpenSettings({ADDON_ID})")


def is_auto_play():
    return get_setting("auto_play")


def get_int_setting(setting):
    return int(get_setting(setting))


def update_delay(fallback=45):
    return get_property("update.delay") or fallback


def update_action(fallback=2):
    return get_property("update.action") or fallback


def is_cache_enabled():
    return get_setting("cache_enabled")


def cache_clear_update():
    return get_setting("clear_cache_update")


def get_cache_expiration():
    return get_int_setting("cache_expiration")


def get_jackett_timeout():
    return get_int_setting("jackett_timeout")


def get_prowlarr_timeout():
    return get_int_setting("prowlarr_timeout")


def trakt_client():
    return get_setting("trakt_client", "")


def trakt_secret():
    return get_setting("trakt_secret", "")


def trakt_lists_sort_order(setting):
	return int(get_setting('trakt_sort_%s' % setting, '0'))