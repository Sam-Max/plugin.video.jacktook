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
                updates_check_addon()
                break

            set_property_no_fallback(first_run_update_prop, "true")
            kodilog("Update Check Service Finished")
        except Exception as e:
            kodilog(e)


def TMDBHelperAutoInstall():
    try:
        _ = xbmcaddon.Addon("plugin.video.themoviedb.helper")
    except RuntimeError:
        return

    tmdb_helper_path = "special://home/addons/plugin.video.themoviedb.helper/resources/players/jacktook.select.json"
    if xbmcvfs.exists(tmdb_helper_path):
        return
    jacktook_select_path = (
        "special://home/addons/plugin.video.jacktook/jacktook.select.json"
    )
    if not xbmcvfs.exists(jacktook_select_path):
        kodilog("jacktook.select.json file not found!")
        return

    ok = xbmcvfs.copy(jacktook_select_path, tmdb_helper_path)
    if not ok:
        kodilog("Error installing jacktook.select.json file!")
        return


class DownloaderSetup:
    def run(self):
        download_dir = get_setting("download_dir")
        translated_path = translatePath(download_dir)
        if not xbmcvfs.exists(translated_path):
            xbmcvfs.mkdir(translated_path)


class JacktookMOnitor(xbmc.Monitor):
    def __init__(self):
        xbmc.Monitor.__init__(self)
        self.startServices()

    def startServices(self):
        CheckKodiVersion().run()
        DatabaseSetup().run()
        Thread(target=UpdateCheck().run).start()
        DownloaderSetup().run()
        TMDBHelperAutoInstall()

    def onScreensaverActivated(self):
        set_property_no_fallback(pause_services_prop, 'true')
        kodilog("PAUSING Jacktook Services Due to Device Sleep")
        
    def onScreensaverDeactivated(self):
        clear_property(pause_services_prop)
        kodilog("UNPAUSING Jacktook Services Due to Device Awake")
        
    def onNotification(self, sender, method, data):
        if method == 'System.OnSleep':
            set_property_no_fallback(pause_services_prop, "true")
            kodilog("PAUSING Jacktook Services Due to Device Sleep")
        elif method == 'System.OnWake':
            clear_property(pause_services_prop)
            kodilog("UNPAUSING Jacktook Services Due to Device Awake")


JacktookMOnitor().waitForAbort()
