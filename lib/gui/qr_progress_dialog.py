import xbmcgui

from lib.utils.kodi.utils import translation


class QRProgressDialog(xbmcgui.WindowXMLDialog):
    def __init__(
        self,
        xml_file: str,
        location: str,
    ):
        super().__init__(xml_file, location)
        self.title = translation(90558)
        self.message = ""
        self.progress = 0
        self.iscanceled = False
        self.qr_image_path = ""

    def setup(self, title, qr_code, url, user_code="", debrid_type="", is_debrid=True):
        self.title = title
        self.qr_image_path = qr_code
        if is_debrid:
            if debrid_type == "RealDebrid":
                self.message = "%s\n\n%s" % (
                    translation(90541) % "https://real-debrid.com/device",
                    translation(90542) % user_code,
                )
            else:
                self.message = translation(90555) % (url, user_code)
        else:
            # For non-debrid services (like Trakt)
            if user_code:
                self.message = translation(90556) % (url, user_code)
            else:
                self.message = translation(90557) % url

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
