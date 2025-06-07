from lib.utils.kodi.utils import kodilog
import xbmcgui


class CustomProgressDialog(xbmcgui.WindowXMLDialog):
    def __init__(self, xml_file: str, location: str):
        super().__init__(xml_file, location)
        self.title = "Downloading"
        self.message = "Please wait..."
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
        self.setFocusId(12003)

    def update_progress(self, percent, message=None):
        self.progress = percent
        self.getControl(12004).setPercent(percent)
        if message:
            self.getControl(12002).setLabel(message)

    def onClick(self, controlId):
        kodilog(f"Control clicked: {controlId}")
        if controlId == 12003:  # Cancel button
            self.cancelled = True
            self.close_dialog()
        elif controlId == 12005:  # Close button
            self.close_dialog()

    def onAction(self, action):
        kodilog(f"Action received: {action.getId()}")
        if action.getId() in (10, 92):
            self.close_dialog()
