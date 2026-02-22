from threading import Thread
from lib.api.trakt.base_cache import setup_databases
from lib.utils.kodi.utils import (
    get_kodi_version,
    get_property_no_fallback,
    get_setting,
    kodilog,
    clear_property,
    dialog_ok,
    set_property_no_fallback,
    translatePath,
)
from time import time
from lib.utils.kodi.settings import update_delay
from lib.updater import updates_check_addon
from lib.services.trakt_sync import TraktSyncService
from lib.services.preloader import StartupPreloader


import xbmcaddon
import xbmcvfs
import xbmc

first_run_update_prop = "jacktook.first_run_update"
pause_services_prop = "jacktook.pause_services"


class CheckKodiVersion:
    def run(self):
        kodilog("Checking Kodi version...")
        if get_kodi_version() < 20:
            dialog_ok(
                heading="Jacktook",
                line1="Kodi 20 or above required. Please update Kodi to use thid addon-",
            )


class DatabaseSetup:
    def run(self):
        setup_databases()


class UpdateCheck:
    def run(self):
        kodilog("Update Check Service Started...")
        if get_property_no_fallback(first_run_update_prop) == "true":
            kodilog("Update check already performed, skipping...")
            return

        try:
            end_pause = time() + update_delay()
            monitor = xbmc.Monitor()
            player = xbmc.Player()

            while not monitor.abortRequested():
                while time() < end_pause:
                    monitor.waitForAbort(1)
                while player.isPlayingVideo():
                    monitor.waitForAbort(1)
                updates_check_addon(automatic=True)
                break

            set_property_no_fallback(first_run_update_prop, "true")
            kodilog("Update Check Service Finished")
        except Exception as e:
            kodilog(e)


def TMDBHelperAutoInstall():
    jacktook_select_path = (
        "special://home/addons/plugin.video.jacktook/jacktook.select.json"
    )

    if not xbmcvfs.exists(jacktook_select_path):
        kodilog("jacktook.select.json file not found!")
        return

    target_addons = [
        "plugin.video.themoviedb.helper",
        "plugin.video.tmdb.bingie.helper",
    ]

    for addon_id in target_addons:
        try:
            _ = xbmcaddon.Addon(addon_id)
        except RuntimeError:
            kodilog(f"{addon_id} addon not found, skipping auto-install.")
            continue

        tmdb_helper_path = (
            f"special://home/addons/{addon_id}/resources/players/jacktook.select.json"
        )

        if xbmcvfs.exists(tmdb_helper_path):
            continue

        ok = xbmcvfs.copy(jacktook_select_path, tmdb_helper_path)
        if ok:
            kodilog(f"Installed jacktook.select.json file to {addon_id}!")
        else:
            kodilog(f"Error installing jacktook.select.json file to {addon_id}!")


class DownloaderSetup:
    def run(self):
        download_dir = get_setting("download_dir")
        translated_path = translatePath(download_dir)
        if not xbmcvfs.exists(translated_path):
            xbmcvfs.mkdir(translated_path)


class DebridExpirationCheck:
    def run(self):
        kodilog("Debrid Expiration Check Service Started...")
        if not get_setting("debrid_expiration_enabled"):
            return

        try:
            threshold = int(get_setting("debrid_expiration_threshold", 3))

            # Reusable notification function
            def notify_expiration(name, days):
                from lib.utils.kodi.utils import notification, translation

                if days == 0:
                    msg = translation(90231) % name
                else:
                    msg = translation(90230) % (name, days)
                notification(msg, time=5000)

            # Check Real-Debrid
            if get_setting("real_debrid_enabled") and get_setting("real_debrid_token"):
                from lib.api.debrid.realdebrid import RealDebrid

                rd = RealDebrid(get_setting("real_debrid_token"))
                days = rd.days_remaining()
                if days is not None and days <= threshold:
                    notify_expiration("Real-Debrid", days)

            # Check AllDebrid
            if get_setting("alldebrid_enabled") and get_setting("alldebrid_token"):
                from lib.api.debrid.alldebrid import AllDebrid

                ad = AllDebrid(get_setting("alldebrid_token"))
                days = ad.days_remaining()
                if days is not None and days <= threshold:
                    notify_expiration("AllDebrid", days)

            # Check TorBox
            if get_setting("torbox_enabled") and get_setting("torbox_token"):
                from lib.api.debrid.torbox import Torbox

                tb = Torbox(get_setting("torbox_token"))
                days = tb.days_remaining()
                if days is not None and days <= threshold:
                    notify_expiration("Torbox", days)

            # Check Premiumize
            if get_setting("premiumize_enabled") and get_setting("premiumize_token"):
                from lib.api.debrid.premiumize import Premiumize

                pm = Premiumize(get_setting("premiumize_token"))
                days = pm.days_remaining()
                if days is not None and days <= threshold:
                    notify_expiration("Premiumize", days)

            # Check Debrider (debrider.app)
            if get_setting("debrider_enabled") and get_setting("debrider_token"):
                from lib.api.debrid.debrider import Debrider

                db = Debrider(get_setting("debrider_token"))
                days = db.days_remaining()
                if days is not None and days <= threshold:
                    notify_expiration("Debrider", days)

        except Exception as e:
            kodilog(f"Error in DebridExpirationCheck: {e}")


class JacktookMOnitor(xbmc.Monitor):
    def __init__(self):
        xbmc.Monitor.__init__(self)
        self.startServices()

    def startServices(self):
        CheckKodiVersion().run()
        DatabaseSetup().run()
        Thread(target=UpdateCheck().run).start()
        Thread(target=TraktSyncService().run).start()
        Thread(target=DebridExpirationCheck().run).start()
        StartupPreloader().run()
        DownloaderSetup().run()
        TMDBHelperAutoInstall()

    def onScreensaverActivated(self):
        set_property_no_fallback(pause_services_prop, "true")
        kodilog("PAUSING Jacktook Services Due to Device Sleep")

    def onScreensaverDeactivated(self):
        clear_property(pause_services_prop)
        kodilog("UNPAUSING Jacktook Services Due to Device Awake")

    def onNotification(self, sender, method, data):
        if method == "System.OnSleep":
            set_property_no_fallback(pause_services_prop, "true")
            kodilog("PAUSING Jacktook Services Due to Device Sleep")
        elif method == "System.OnWake":
            clear_property(pause_services_prop)
            kodilog("UNPAUSING Jacktook Services Due to Device Awake")


JacktookMOnitor().waitForAbort()
