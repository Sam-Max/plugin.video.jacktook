from lib.utils.kodi.utils import get_setting, execute_builtin
from lib.utils.kodi.logging import kodilog
import xbmc


class AutoStartService:
    def run(self):
        if get_setting("auto_start_jacktook", False):
            kodilog("AutoStart: Launching Jacktook on boot...", level=xbmc.LOGINFO)
            execute_builtin("RunAddon(plugin.video.jacktook)")
        else:
            kodilog("AutoStart: Disabled by user.", level=xbmc.LOGINFO)
