import abc
import xbmcgui
from lib.gui.base_window import BaseWindow


class SourcePackWindow(BaseWindow):
    def __init__(self, xml_file, location, source=None, pack_info=None, item_information=None):
        super().__init__(xml_file, location, item_information=item_information)
        self.pack_info = pack_info
        self.source = source
        self.display_list = None

    def onInit(self):
        self.display_list = self.getControlList(1000)
        self.populate_sources_list()

        self.set_default_focus(self.display_list, 1000, control_list_reset=True)
        super().onInit()

    def populate_sources_list(self):
        self.display_list.reset()

        for file_tuple in self.pack_info["files"]:
            _, title= file_tuple
            menu_item = xbmcgui.ListItem(label=title)
            menu_item.setProperty("title", title)
            menu_item.setProperty("type", self.source.type)
            menu_item.setProperty("quality", self.source.quality)
            self.display_list.addItem(menu_item)

    @abc.abstractmethod
    def handle_action(self, action_id, control_id=None):
        pass
