import abc
import xbmcgui
from lib.gui.base_window import BaseWindow
from lib.utils.debrid_utils import get_debrid_status
from lib.utils.kodi_utils import bytes_to_human_readable
from lib.utils.utils import extract_publish_date, get_colored_languages, get_random_color


class SourceWindow(BaseWindow):
    """
    Common window class for source selection type windows.
    """

    def __init__(self, xml_file, location, item_information=None, sources=None):
        super().__init__(xml_file, location, item_information=item_information)
        self.sources = sources or []
        self.item_information = item_information
        self.display_list = None

    def onInit(self):
        self.display_list = self.getControlList(1000)
        self.populate_sources_list()

        self.set_default_focus(self.display_list, 1000, control_list_reset=True)
        super().onInit()

    def populate_sources_list(self):
        self.display_list.reset()

        for source in self.sources:
            menu_item = xbmcgui.ListItem(label=f"{source['title']}")

            for info in source:
                value = source[info]
                if info == "publishDate":
                    value = extract_publish_date(value)
                if info == "size":
                    value = bytes_to_human_readable(value)
                if info in ["indexer", "provider", "type"]:
                    color = get_random_color(value)
                    value = f"[B][COLOR {color}]{value}[/COLOR][/B]"
                if info == "fullLanguages":
                    value = get_colored_languages(value)
                    if len(value) <= 0: 
                        value = ""
                if info == "isCached":
                    info = "status"
                    value = get_debrid_status(source)

                menu_item.setProperty(info, str(value))

            self.display_list.addItem(menu_item)

    @abc.abstractmethod
    def handle_action(self, action_id, control_id=None):
        pass
