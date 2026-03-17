from lib.utils.kodi.utils import (
    get_setting,
    set_setting,
    kodilog,
)


def _migrate_trakt_credentials():
    DEFAULT_CLIENT = (
        "687c707dc7073be777a6dd6869ffd9034109d75dcda6599a7273f49a68266ff8"
    )
    DEFAULT_SECRET = (
        "3191ae63a3cf60d767b1d6fc1e39b1dedc6f3346b826d62901f9f2c3c9925e26"
    )

    current_client = get_setting("trakt_client", "")
    current_secret = get_setting("trakt_secret", "")

    client_needs_reset = current_client != DEFAULT_CLIENT or current_client == ""
    secret_needs_reset = current_secret != DEFAULT_SECRET or current_secret == ""

    if not (client_needs_reset or secret_needs_reset):
        kodilog("Trakt credentials already customized by user, skipping migration")
        return

    kodilog("Migrating Trakt credentials to force re-authentication")

    if client_needs_reset:
        set_setting("trakt_client", "")

    if secret_needs_reset:
        set_setting("trakt_secret", "")

    set_setting("trakt_client", DEFAULT_CLIENT)
    set_setting("trakt_secret", DEFAULT_SECRET)

def run_migrations():
    _migrate_trakt_credentials()
    kodilog(f"Trakt migration complete")
