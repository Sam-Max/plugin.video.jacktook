from xbmcgui import WindowXMLDialog, WindowXML
import xbmcgui


class CustomWindow(WindowXML):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def onInit(self):
        pass


class MyWindow(WindowXML):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.list_control = None

    def onInit(self):
        self.list_control = self.getControl(32503)

    def add_item(self, list_item):
        if self.list_control:
            self.list_control.addItem(list_item)

    def onClick(self, control_id):
        if control_id == 32503:  # List control
            selected_item = self.list_control.getSelectedItem()
            if selected_item:
                xbmcgui.Dialog().notification(
                    "Selected Item",
                    selected_item.getLabel(),
                    xbmcgui.NOTIFICATION_INFO,
                    3000,
                )


class CustomDialog(WindowXMLDialog):
    _heading = 32500
    _text = 32501
    _close_button_id = 32503

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.heading = kwargs.get("heading")
        self.text = kwargs.get("text")

    def onInit(self):
        self.getControl(self._heading).setLabel(self.heading)
        self.getControl(self._text).setLabel(self.text)

    def onClick(self, controlId):
        if controlId == self._close_button_id:
            self.close()
