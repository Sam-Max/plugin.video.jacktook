from datetime import timedelta
from lib.api.stremio.api_client import Stremio
from lib.db.cached import cache
from lib.utils.kodi.utils import (
    get_setting,
    kodilog,
    set_setting,
    translation,
)
from lib.clients.stremio.constants import (
    STREMIO_ADDONS_KEY,
    STREMIO_ADDONS_CATALOGS_KEY,
    STREMIO_USER_ADDONS,
)
from lib.clients.stremio.helpers import merge_addons_lists
import xbmcgui


def stremio_login(params):
    dialog = xbmcgui.Dialog()
    dialog.ok(
        translation(90612),
        translation(90613)
    )

    email = dialog.input(heading=translation(90614), type=xbmcgui.INPUT_ALPHANUM)
    if not email:
        return

    password = dialog.input(heading=translation(90615), type=xbmcgui.INPUT_ALPHANUM)
    if not password:
        return

    log_in(email, password, dialog)


def log_in(email, password, dialog):
    try:
        stremio = Stremio()
        stremio.login(email, password)
    except Exception as e:
        dialog.ok(translation(90616), translation(90617) % e)
        return

    try:
        # Only merge user account addons with custom addons
        user_account_addons = stremio.get_my_addons() or []
        all_user_addons = cache.get(STREMIO_USER_ADDONS) or []
        custom_addons = [
            a for a in all_user_addons if a.get("transportName") == "custom"
        ]
        all_addons = merge_addons_lists(user_account_addons, custom_addons)
        cache.set(STREMIO_USER_ADDONS, all_addons, timedelta(days=365 * 20))

        set_setting("stremio_email", email)
        set_setting("stremio_pass", password)
        set_setting("stremio_loggedin", "true")

        kodilog(f"Stremio addons imported: {len(all_addons)}")
    except Exception as e:
        dialog.ok(
            translation(90618),
            translation(90619),
        )
        kodilog(f"Failed to import addons: {e}")
        return

    dialog.ok(translation(90620), translation(90621))


def stremio_update(params):
    dialog = xbmcgui.Dialog()
    confirm = dialog.yesno(
        translation(90622),
        translation(90623),
        nolabel=translation(90242),
        yeslabel=translation(32043),
    )
    if not confirm:
        return

    email = get_setting("stremio_email")
    password = get_setting("stremio_pass")

    log_in(email, password, dialog)


def stremio_logout(params):
    dialog = xbmcgui.Dialog()

    confirm = dialog.yesno(
        translation(90624),
        translation(90625),
        nolabel=translation(90242),
        yeslabel=translation(90626),
    )
    if confirm:
        cache.set(STREMIO_ADDONS_KEY, None, timedelta(seconds=1))
        cache.set(STREMIO_ADDONS_CATALOGS_KEY, None, timedelta(seconds=1))
        # Do not clear custom addons, only clear login state and user (login) addons
        all_user_addons = cache.get(STREMIO_USER_ADDONS) or []
        custom_addons = [
            a for a in all_user_addons if a.get("transportName") == "custom"
        ]
        cache.set(STREMIO_USER_ADDONS, custom_addons, timedelta(days=365 * 20))

        set_setting("stremio_loggedin", "false")
        set_setting("stremio_email", "")
        set_setting("stremio_pass", "")
