import xbmc
import xbmcgui

from lib.utils.kodi.utils import ADDON_PATH, kodilog


ACTION_PREVIOUS_MENU = 10
ACTION_PLAYER_STOP = 13
ACTION_NAV_BACK = 92


class SkipIntroWindow(xbmcgui.WindowXMLDialog):
    """
    Overlay dialog that shows a 'Skip Intro' or 'Skip Recap' button
    during playback when IntroDB segment data is available.
    """

    def __init__(self, xml_file, xml_location, segment_data=None, label="Skip Intro"):
        super().__init__(xml_file, xml_location)
        self.segment_data = segment_data or {}
        self.label = label
        self.action = None
        self.closed = False
        self.player = xbmc.Player()

    def onInit(self):
        self.setProperty("skip_label", self.label)
        self._background_monitor()

    def _background_monitor(self):
        """Monitor playback and auto-close when segment ends or playback stops."""
        try:
            end_sec = self.segment_data.get("end_sec", 0)

            while not self.closed and self.player.isPlaying():
                try:
                    current_time = self.player.getTime()
                except RuntimeError:
                    break

                # Auto-close if we've passed the segment end
                if current_time >= end_sec:
                    break

                xbmc.sleep(500)
        except Exception as e:
            kodilog(f"SkipIntroWindow monitor error: {e}")

        if not self.closed:
            self.close()

    def onClick(self, control_id):
        if control_id == 4001:
            # Skip button pressed
            self.action = "skip"
            self._do_skip()
            self.close()
        elif control_id == 4002:
            # Dismiss button pressed
            self.action = "dismiss"
            self.close()

    def onAction(self, action):
        action_id = action.getId()
        if action_id in (ACTION_PREVIOUS_MENU, ACTION_PLAYER_STOP, ACTION_NAV_BACK):
            self.action = "dismiss"
            self.close()

    def _do_skip(self):
        """Seek to the end of the current segment."""
        try:
            end_sec = self.segment_data.get("end_sec", 0)
            if end_sec > 0 and self.player.isPlaying():
                self.player.seekTime(end_sec)
                kodilog(f"SkipIntroWindow: Skipped to {end_sec}s")
        except Exception as e:
            kodilog(f"SkipIntroWindow: Error seeking: {e}")

    def close(self):
        self.closed = True
        super().close()
