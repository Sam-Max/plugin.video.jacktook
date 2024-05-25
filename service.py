import xbmc
from threading import Thread
from lib.utils.kodi_utils import (
    get_kodi_version,
    get_property,
    set_property,
    clear_property,
    dialog_ok
)
from time import time
from lib.api.jacktook.kodi import kodilog
from lib.utils.settings import update_action, update_delay
from lib.updater import updates_check_addon


first_run_update_prop = "jacktook.first_run_update"
pause_services_prop= "jacktook.pause_services"


class OnNotificationActions:
    def run(self, sender, method, data):
        if sender == "xbmc":
            if method in ("GUI.OnScreensaverActivated", "System.OnSleep"):
                set_property(pause_services_prop, "true")
            elif method in ("GUI.OnScreensaverDeactivated", "System.OnWake"):
                clear_property(pause_services_prop)


class CheckKodiVersion:
    def run(self):
        kodilog("Checking Kodi version")
        if get_kodi_version() < 20:
            dialog_ok(
                "Jacktook",
                "Kodi 20 or above required[CR]Please update Kodi to use addon",
            )


class UpdateCheck:
    def run(self):
        kodilog("Update Check Service Started")
        if get_property(first_run_update_prop) == "true":
            return
        end_pause = time() + update_delay()
        monitor, player = xbmc.Monitor(), xbmc.Player()
        wait_for_abort, is_playing = monitor.waitForAbort, player.isPlayingVideo
        while not monitor.abortRequested():
            while time() < end_pause:
                wait_for_abort(1)
            while get_property(pause_services_prop) == "true" or is_playing():
                wait_for_abort(1)
            updates_check_addon(update_action())
            break
        set_property(first_run_update_prop, "true")
        try:
            del monitor
        except:
            pass
        try:
            del player
        except:
            pass
        kodilog("Update Check Service Finished")


class JacktookMOnitor(xbmc.Monitor):
    def __init__(self):
        xbmc.Monitor.__init__(self)
        self.start()

    def start(self):
        CheckKodiVersion().run()
        Thread(target=UpdateCheck().run).start()

    def onNotification(self, sender, method, data):
        OnNotificationActions().run(sender, method, data)


JacktookMOnitor().waitForAbort()
