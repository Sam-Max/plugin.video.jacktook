from lib.gui.base_window import BaseWindow

class ResumeDialog(BaseWindow):
    def __init__(self, xml_file, xml_location, **kwargs):
        super().__init__(xml_file, xml_location)
        self.resume = None
        self.resume_percent = kwargs.get("resume_percent", 0.0)

    def doModal(self):
        super().doModal()

    def onInit(self):
        super().onInit()
        self.getControl(1002).setLabel(
            f"Resume from {self.resume_percent:.1f}%"
        )  # Resume Button
        self.getControl(1003).setLabel("Start from Beginning")  # Start Button

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
