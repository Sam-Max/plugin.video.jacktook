import abc
import xbmcgui
from lib.gui.base_window import BaseWindow


class SourcePackWindow(BaseWindow):
    def __init__(self, xml_file, location, source=None, pack_info=None, item_information=None):
        super().__init__(xml_file, location, item_information=item_information)
        self.pack_info = pack_info or {"files": []}  
        self.source = source or type("EmptySource", (), {"type": "", "quality": ""})()
        self.display_list = None

    def onInit(self):
        self.display_list = self.getControlList(1000)
        self.populate_sources_list()
        self.set_default_focus(self.display_list, 1000, control_list_reset=True)
        super().onInit()

    def populate_sources_list(self):
        self.display_list.reset()

        files = self.pack_info.get("files", [])
        for _, title in files:
            menu_item = xbmcgui.ListItem(label=title)
            menu_item.setProperty("title", title or "")
            menu_item.setProperty("type", getattr(self.source, "type", "") or "")
            menu_item.setProperty("quality", getattr(self.source, "quality", "") or "")
            self.display_list.addItem(menu_item)

    @abc.abstractmethod
    def handle_action(self, action_id, control_id=None):
        """Subclasses must implement this to handle user actions."""
        pass
