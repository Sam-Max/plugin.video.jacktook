from time import time
import xbmc

from lib.utils.kodi.utils import (
    execute_builtin,
    get_property,
    get_setting,
    kodilog,
    notification,
)


class WidgetRefreshService:
    def run(self):
        kodilog("WidgetRefresh Service Starting...", level=xbmc.LOGINFO)
        monitor = xbmc.Monitor()
        player = xbmc.Player()
        wait_for_abort = monitor.waitForAbort

        wait_for_abort(10)
        self.set_next_refresh(time())

        while not monitor.abortRequested():
            try:
                wait_for_abort(10)
                offset = int(get_setting("widget_refresh_timer", 60))
                if offset != getattr(self, "offset", None):
                    self.set_next_refresh(time())
                    continue
                if self.condition_check(player):
                    continue
                if self.next_refresh < time():
                    kodilog("WidgetRefresh Service - Refreshing widgets...", level=xbmc.LOGINFO)
                    self.refresh_widgets()
                    self.set_next_refresh(time())
            except Exception as e:
                kodilog(f"WidgetRefresh error: {e}", level=xbmc.LOGERROR)

        try:
            del monitor
        except:
            pass
        try:
            del player
        except:
            pass
        kodilog("WidgetRefresh Service Finished", level=xbmc.LOGINFO)

    def condition_check(self, player):
        container_plugin = xbmc.getInfoLabel("Container.PluginName")

        # No refrescar si estamos dentro de Jacktook
        if "jacktook" in container_plugin:
            return True

        # No refrescar si está reproduciendo vídeo
        if player.isPlayingVideo():
            return True

        # No refrescar si los servicios están pausados (screensaver/sleep)
        if get_property("jacktook.pause_services") == "true":
            return True

        # No refrescar si el timer es 0 (desactivado)
        if self.next_refresh is None:
            return True

        return False

    def set_next_refresh(self, _time):
        self.offset = int(get_setting("widget_refresh_timer", 60))
        if self.offset:
            self.next_refresh = _time + (self.offset * 60)
        else:
            self.next_refresh = None

    def refresh_widgets(self):
        execute_builtin("UpdateLibrary(video,special://skin/foo)")
        if get_setting("widget_refresh_notification", True):
            notification("Widgets Refreshed", time=2500)
