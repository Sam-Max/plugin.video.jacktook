from threading import Thread
from time import time
import os

import xbmc
import xbmcaddon
import xbmcvfs

from lib.api.trakt.base_cache import setup_databases
from lib.services.migrations import run_migrations
from lib.services.preloader import StartupPreloader
from lib.services.trakt_sync import TraktSyncService
from lib.updater import updates_check_addon
from lib.utils.kodi.settings import update_delay
from lib.utils.kodi.utils import (
    clear_cached_settings,
    clear_property,
    dialog_ok,
    get_kodi_version,
    get_property_no_fallback,
    get_setting,
    kodilog,
    set_property_no_fallback,
    translation,
    translatePath,
)


first_run_update_prop = "jacktook.first_run_update"
pause_services_prop = "jacktook.pause_services"


class CheckKodiVersion:
    def run(self):
        kodilog("Checking Kodi version...")
        if get_kodi_version() < 20:
            dialog_ok(
                heading=xbmcaddon.Addon().getAddonInfo("name"),
                line1=translation(90559),
            )


class DatabaseSetup:
    def run(self):
        setup_databases()


class UpdateCheck:
    def run(self):
        kodilog("Update Check Service Started...", level=xbmc.LOGINFO)
        if get_property_no_fallback(first_run_update_prop) == "true":
            kodilog("Update check already performed, skipping...", level=xbmc.LOGINFO)
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
                set_property_no_fallback(first_run_update_prop, "true")
                updates_check_addon(automatic=True)
                break

            kodilog("Update Check Service Finished", level=xbmc.LOGINFO)
        except Exception as e:
            kodilog(e, level=xbmc.LOGERROR)


def TMDBHelperAutoInstall():
    jacktook_select_path = (
        "special://home/addons/plugin.video.jacktook/jacktook.select.json"
    )

    if not xbmcvfs.exists(jacktook_select_path):
        kodilog("jacktook.select.json file not found!", level=xbmc.LOGERROR)
        return

    target_addons = [
        "plugin.video.themoviedb.helper",
        "plugin.video.tmdb.bingie.helper",
    ]

    source_content = _read_text_file(jacktook_select_path)
    if source_content is None:
        kodilog("Unable to read bundled jacktook.select.json", level=xbmc.LOGERROR)
        return

    for addon_id in target_addons:
        try:
            _ = xbmcaddon.Addon(addon_id)
        except RuntimeError:
            kodilog(
                f"{addon_id} addon not found, skipping auto-install.",
                level=xbmc.LOGINFO,
            )
            continue

        tmdb_helper_path = (
            f"special://home/addons/{addon_id}/resources/players/jacktook.select.json"
        )

        target_content = _read_text_file(tmdb_helper_path)
        if target_content == source_content:
            continue

        target_dir = os.path.dirname(translatePath(tmdb_helper_path))
        if target_dir and not xbmcvfs.exists(target_dir):
            xbmcvfs.mkdirs(target_dir)

        if xbmcvfs.exists(tmdb_helper_path):
            xbmcvfs.delete(tmdb_helper_path)

        ok = xbmcvfs.copy(jacktook_select_path, tmdb_helper_path)
        if ok:
            kodilog(
                f"Installed or updated jacktook.select.json file for {addon_id}!",
                level=xbmc.LOGINFO,
            )
        else:
            kodilog(
                f"Error installing jacktook.select.json file for {addon_id}!",
                level=xbmc.LOGERROR,
            )


def _read_text_file(path):
    translated_path = translatePath(path)
    if not translated_path or not os.path.exists(translated_path):
        return None

    try:
        with open(translated_path, "r", encoding="utf-8") as file_obj:
            return file_obj.read()
    except OSError as error:
        kodilog(f"Failed to read {path}: {error}", level=xbmc.LOGERROR)
        return None


class DownloaderSetup:
    def run(self):
        download_dir = get_setting("download_dir")
        translated_path = translatePath(download_dir)
        if not xbmcvfs.exists(translated_path):
            xbmcvfs.mkdir(translated_path)


class DebridExpirationCheck:
    def run(self):
        kodilog("Debrid Expiration Check Service Started...", level=xbmc.LOGINFO)
        if not get_setting("debrid_expiration_enabled"):
            return

        try:
            threshold = int(get_setting("debrid_expiration_threshold", 3))

            def notify_expiration(name, days):
                from lib.utils.kodi.utils import notification, translation

                if days == 0:
                    msg = translation(90231) % name
                else:
                    msg = translation(90230) % (name, days)
                notification(msg, time=5000)

            if get_setting("real_debrid_enabled") and get_setting("real_debrid_token"):
                from lib.api.debrid.realdebrid import RealDebrid

                rd = RealDebrid(str(get_setting("real_debrid_token", "")))
                days = rd.days_remaining()
                if days is not None and days <= threshold:
                    notify_expiration("Real-Debrid", days)

            alldebrid_token = get_setting("alldebrid_token")
            if get_setting("alldebrid_enabled") and alldebrid_token:
                from lib.api.debrid.alldebrid import AllDebrid

                ad = AllDebrid(str(alldebrid_token))
                days = ad.days_remaining()
                if days is not None and days <= threshold:
                    notify_expiration("AllDebrid", days)

            if get_setting("torbox_enabled") and get_setting("torbox_token"):
                from lib.api.debrid.torbox import Torbox

                tb = Torbox(get_setting("torbox_token"))
                days = tb.days_remaining()
                if days is not None and days <= threshold:
                    notify_expiration("Torbox", days)

            if get_setting("premiumize_enabled") and get_setting("premiumize_token"):
                from lib.api.debrid.premiumize import Premiumize

                pm = Premiumize(str(get_setting("premiumize_token", "")))
                days = pm.days_remaining()
                if days is not None and days <= threshold:
                    notify_expiration("Premiumize", days)

            if get_setting("debrider_enabled") and get_setting("debrider_token"):
                from lib.api.debrid.debrider import Debrider

                db = Debrider(get_setting("debrider_token"))
                days = db.days_remaining()
                if days is not None and days <= threshold:
                    notify_expiration("Debrider", days)

        except Exception as e:
            kodilog(f"Error in DebridExpirationCheck: {e}", level=xbmc.LOGERROR)


class JacktookMOnitor(xbmc.Monitor):
    def __init__(self):
        xbmc.Monitor.__init__(self)
        self.startServices()

    def startServices(self):
        CheckKodiVersion().run()
        DatabaseSetup().run()
        run_migrations()
        Thread(target=UpdateCheck().run).start()
        Thread(target=TraktSyncService().run).start()
        Thread(target=DebridExpirationCheck().run).start()
        StartupPreloader().run()
        DownloaderSetup().run()
        TMDBHelperAutoInstall()
        try:
            from lib.services.autostart import AutoStartService
            AutoStartService().run()
        except Exception as e:
            kodilog(f"AutoStart failed: {e}", level=xbmc.LOGERROR)

    def onScreensaverActivated(self):
        set_property_no_fallback(pause_services_prop, "true")
        kodilog(
            "PAUSING Jacktook Services Due to Device Sleep", level=xbmc.LOGINFO
        )

    def onScreensaverDeactivated(self):
        clear_property(pause_services_prop)
        kodilog(
            "UNPAUSING Jacktook Services Due to Device Awake", level=xbmc.LOGINFO
        )

    def onSettingsChanged(self):
        clear_cached_settings()
        from lib.utils.tmdb_init import ensure_tmdb_init
        ensure_tmdb_init()
        kodilog("Cleared cached settings and refreshed TMDB language after Kodi settings change", level=xbmc.LOGINFO)

    def onNotification(self, sender, method, data):
        if method == "System.OnSleep":
            set_property_no_fallback(pause_services_prop, "true")
            kodilog(
                "PAUSING Jacktook Services Due to Device Sleep",
                level=xbmc.LOGINFO,
            )
        elif method == "System.OnWake":
            clear_property(pause_services_prop)
            kodilog(
                "UNPAUSING Jacktook Services Due to Device Awake",
                level=xbmc.LOGINFO,
            )
