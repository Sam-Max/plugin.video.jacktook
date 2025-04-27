import xbmcgui
from lib.gui.base_window import BaseWindow

class FilterWindow(BaseWindow):
    def __init__(self, xml_file, location, filter):
        super().__init__(xml_file, location, None)
        self.filter = filter
        self.selected_quality = None

    def onInit(self):
        self.list_control = self.getControl(2000)
        self.list_control.reset()
        
        for q in self.filter:
            item = xbmcgui.ListItem(label=q)
            self.list_control.addItem(item)
        reset_item = xbmcgui.ListItem(label="Reset Filter")
        
        self.list_control.addItem(reset_item)
        
        self.set_default_focus(self.list_control, 2000, control_list_reset=True)


    def handle_action(self, action_id, control_id=None):
        if action_id == 7:  # Select
            pos = self.list_control.getSelectedPosition()
            if pos < len(self.filter):
                self.selected_filter = self.filter[pos]
            else:
                self.selected_filter = None  # Reset
            self.close()
        elif action_id in (2, 9, 10, 13, 92):  # Back/Escape
            self.close()