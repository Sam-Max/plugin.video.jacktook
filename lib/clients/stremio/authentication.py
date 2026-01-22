from datetime import timedelta
from lib.api.stremio.api_client import Stremio
from lib.db.cached import cache
from lib.utils.kodi.utils import (
    get_setting,
    kodilog,
    set_setting,
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
        "Stremio Add-ons Import",
        "To import your add-ons, please log in with your Stremio email and password."
    )

    email = dialog.input(heading="Enter your Email", type=xbmcgui.INPUT_ALPHANUM)
    if not email:
        return

    password = dialog.input(heading="Enter your Password", type=xbmcgui.INPUT_ALPHANUM)
    if not password:
        return

    log_in(email, password, dialog)


def log_in(email, password, dialog):
    try:
        stremio = Stremio()
        stremio.login(email, password)
    except Exception as e:
        dialog.ok("Login Failed", f"Failed to login: {e}")
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
            "Add-ons Import Failed",
            "Please try again later and report the issue if the problem persists. For more details, check the log file.",
        )
        kodilog(f"Failed to import addons: {e}")
        return

    dialog.ok("Addons Imported", f"Successfully imported addons from your account.")


def stremio_update(params):
    dialog = xbmcgui.Dialog()
    confirm = dialog.yesno(
        "Update Stremio Addons",
        "Do you want to update the Addons from you account?",
        nolabel="Cancel",
        yeslabel="Yes",
    )
    if not confirm:
        return

    email = get_setting("stremio_email")
    password = get_setting("stremio_pass")

    log_in(email, password, dialog)


def stremio_logout(params):
    dialog = xbmcgui.Dialog()

    confirm = dialog.yesno(
        "Log Out from Stremio",
        "Are you sure you want to log out? You can continue using Stremio without logging in, but your settings will be reset to the default configuration.",
        nolabel="Cancel",
        yeslabel="Log Out",
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
