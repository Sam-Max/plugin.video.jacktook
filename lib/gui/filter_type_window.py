import xbmcgui
from lib.gui.base_window import BaseWindow


class FilterTypeWindow(BaseWindow):
    def __init__(self, xml_file, location):
        super().__init__(xml_file, location, None)
        self.selected_type = None

    def onInit(self):
        self.list_control = self.getControl(2000)
        self.list_control.reset()
        
        quality_item = xbmcgui.ListItem(label="Filter by Quality")
        quality_item.setProperty("type", "quality")
        self.list_control.addItem(quality_item)
        
        provider_item = xbmcgui.ListItem(label="Filter by Provider")
        provider_item.setProperty("type", "provider")
        self.list_control.addItem(provider_item)

        source_item = xbmcgui.ListItem(label="Filter by Source")
        source_item.setProperty("type", "indexer")
        self.list_control.addItem(source_item)

        language_item = xbmcgui.ListItem(label="Filter by Language")
        language_item.setProperty("type", "language")
        self.list_control.addItem(language_item)

        torrents_item = xbmcgui.ListItem(label="Filter by Torrents")
        torrents_item.setProperty("type", "only_torrents")
        self.list_control.addItem(torrents_item)

        debrid_item = xbmcgui.ListItem(label="Filter by Debrid")
        debrid_item.setProperty("type", "only_debrid")
        self.list_control.addItem(debrid_item)
        
        reset_item = xbmcgui.ListItem(label="Reset Filter")
        reset_item.setProperty("type", "reset")
        self.list_control.addItem(reset_item)

        self.set_default_focus(self.list_control, 2000, control_list_reset=True)

    def handle_action(self, action_id, control_id=None):
        if action_id == 7:  # Select
            selected_item = self.list_control.getSelectedItem()
            if selected_item:
                self.selected_type = selected_item.getProperty("type")
                if self.selected_type == "reset":
                    self.selected_type = None
            self.close()
        elif action_id in (2, 9, 10, 13, 92):  # Back/Escape
            self.close()