from lib.utils.general.utils import DebridType, IndexerType
import xbmcgui


class QRProgressDialog(xbmcgui.WindowXMLDialog):
    def __init__(
        self,
        xml_file: str,
        location: str,
    ):
        super().__init__(xml_file, location)
        self.title = "QR Code Authentication"
        self.message = ""
        self.progress = 0
        self.iscanceled = False
        self.qr_image_path = ""

    def setup(self, title, qr_code, auth_url, user_code, debrid_type):
        """Set all custom data after initialization."""
        self.title = title
        self.qr_image_path = qr_code
        if debrid_type == DebridType.RD:
            self.message = f"Navigate to: https://real-debrid.com/device\n\nEnter the following code: [COLOR seagreen][B]{user_code}[/B][/COLOR]"
        else:
            self.message = f"Go to:\n[COLOR cyan]{auth_url}[/COLOR]\nEnter code: [COLOR seagreen][B]{user_code}[/B][/COLOR]"

    def show_dialog(self):
        self.show()
        self.onInit()

    def close_dialog(self):
        self.close()

    def onInit(self):
        self.getControl(12001).setLabel(self.title)  # Title label
        self.getControl(12002).setLabel(self.message)  # Message / instructions
        self.getControl(12004).setPercent(self.progress)  # Progress bar
        if self.qr_image_path:
            self.getControl(12006).setImage(self.qr_image_path)  # QR image
        self.setFocusId(12003)  # Focus on Close button

    def update_progress(self, percent, message=None):
        self.progress = percent
        self.getControl(12004).setPercent(percent)
        if message:
            self.getControl(12002).setLabel(message)

    def onClick(self, controlId):
        if controlId == 12003:  # Close button
            self.iscanceled = True
            self.close_dialog()

    def onAction(self, action):
        if action.getId() in (10, 92):
            self.close_dialog()
