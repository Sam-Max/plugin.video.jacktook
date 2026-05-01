from lib.utils.kodi.utils import kodilog, translation
import xbmcgui


class CustomProgressDialog(xbmcgui.WindowXMLDialog):
    def __init__(self, xml_file: str, location: str):
        super().__init__(xml_file, location)
        self.title = translation(30653)
        self.message = translation(90554)
        self.progress = 0
        self.cancelled = False

    def show_dialog(self):
        self.show()
        self.onInit()

    def close_dialog(self):
        self.close()

    def onInit(self):
        self.getControl(12001).setLabel(self.title)
        self.getControl(12002).setLabel(self.message)
        self.getControl(12004).setPercent(self.progress)
        self.getControl(12006).setLabel(f"{self.progress}%")
        self.setFocusId(12003)

    def update_progress(self, percent, message=None, downloaded_str="", size_str="", speed_str="", eta_str=""):
        self.progress = percent
        try:
            self.getControl(12004).setPercent(percent)
            self.getControl(12006).setLabel(f"{percent}%")
            if message:
                self.getControl(12002).setLabel(message)
            if downloaded_str:
                self.getControl(12007).setLabel(downloaded_str)
            if speed_str:
                self.getControl(12008).setLabel(f"{speed_str}  |  {eta_str}")
        except Exception as e:
            kodilog(f"[CustomProgressDialog] Update error: {e}")

    def onClick(self, controlId):
        if controlId == 12003:  # Cancel button
            self.cancelled = True
            self.close_dialog()
        elif controlId == 12005:  # Close button
            self.close_dialog()

    def onAction(self, action):
        if action.getId() in (10, 92):
            self.close_dialog()