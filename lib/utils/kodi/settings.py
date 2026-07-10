import xbmc

from .utils import ADDON_ID, get_setting, set_setting

EMPTY_USER = "unknown_user"


def addon_settings():
    return xbmc.executebuiltin(f"Addon.OpenSettings({ADDON_ID})")


def auto_play_enabled():
    return get_setting("auto_play")


def subtitle_automation_enabled() -> bool:
    """Return the unified subtitle automation preference.

    Profiles created before the unified setting used either of two independent
    switches. On first use, preserve their effective behavior by migrating the
    logical OR of the existing unified value and those switches into the new
    setting, then use only the new setting thereafter.
    """
    if not get_setting("subtitle_automation_migrated", False):
        enabled = bool(
            get_setting("subtitle_automation", False)
            or get_setting("auto_subtitle_selection", False)
            or get_setting("auto_subtitle_download", False)
        )
        set_setting("subtitle_automation", "true" if enabled else "false")
        set_setting("subtitle_automation_migrated", "true")
        return enabled
    return bool(get_setting("subtitle_automation", False))


def get_int_setting(setting):
    return int(get_setting(setting))


def update_delay(default=45):
    return default


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
    return int(get_setting(f"trakt_sort_{setting}", "0"))


def get_update_action():
    return int(get_setting("update_action", "0"))
