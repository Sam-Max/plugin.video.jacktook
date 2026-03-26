from lib.gui.base_window import BaseWindow
from lib.utils.kodi.utils import translation

class ResumeDialog(BaseWindow):
    def __init__(self, xml_file, xml_location, **kwargs):
        super().__init__(xml_file, xml_location)
        self.resume = None
        self.resume_percent = kwargs.get("resume_percent", 0.0)

    def doModal(self):
        super().doModal()

    def onInit(self):
        super().onInit()
        self.getControl(1002).setLabel(translation(90538) % self.resume_percent)
        self.getControl(1003).setLabel(translation(90539))

    def onClick(self, control_id):
        if control_id == 1002:  # Resume button ID
            self.resume = True
        elif control_id == 1003:  # Start button ID
            self.resume = False
        self.close()

    def handle_action(self, action_id, control_id=None):
        if action_id in (10, 92):  # Back or Escape
            self.resume = None
            self.close()
