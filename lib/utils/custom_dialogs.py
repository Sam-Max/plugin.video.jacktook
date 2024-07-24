from xbmcgui import WindowXMLDialog


class CustomDialog(WindowXMLDialog):
    _heading = 32500
    _text = 32501
    _close_button_id = 32503

    def __init__(self, *args, **kwargs):
        super(CustomDialog, self).__init__(*args, **kwargs)
        self.heading = kwargs.get("heading")
        self.text = kwargs.get("text")

    def onInit(self):
        self.getControl(self._heading).setLabel(self.heading)
        self.getControl(self._text).setLabel(self.text)

    def onClick(self, controlId):
        if controlId == self._close_button_id:
            self.close()
