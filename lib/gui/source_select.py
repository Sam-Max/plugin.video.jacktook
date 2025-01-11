import xbmcgui
from lib.gui.base_window import BaseWindow
from lib.gui.resolver_window import ResolverWindow
from lib.gui.resume_window import ResumeDialog
from lib.utils.kodi_utils import ADDON_PATH, notification
from lib.utils.debrid_utils import get_debrid_status
from lib.utils.kodi_utils import bytes_to_human_readable
from lib.utils.utils import (
    extract_publish_date,
    get_colored_languages,
    get_random_color,
)
from lib.api.jacktook.kodi import kodilog
from lib.api.transmission import queue_torrent_to_transmission
from lib.utils.kodi_utils import get_setting


class SourceSelect(BaseWindow):
    def __init__(
        self, xml_file, location, item_information=None, sources=None, uncached=None
    ):
        super().__init__(xml_file, location, item_information=item_information)
        self.uncached_sources = uncached or []
        self.position = -1
        self.sources = sources
        self.item_information = item_information
        self.playback_info = None
        self.resume = None
        self.CACHE_KEY = (
            self.item_information["tv_data"] or self.item_information["ids"]
        )
        self.setProperty("instant_close", "false")
        self.setProperty("resolving", "false")

    def onInit(self):
        self.display_list = self.getControlList(1000)
        self.populate_sources_list()
        self.set_default_focus(self.display_list, 1000, control_list_reset=True)
        super().onInit()

    def doModal(self):
        super().doModal()
        return self.playback_info

    def populate_sources_list(self):
        self.display_list.reset()

        for source in self.sources:
            menu_item = xbmcgui.ListItem(label=f"{source['title']}")

            for info in source:
                value = source[info]
                if info == "publishDate":
                    value = extract_publish_date(value)
                if info == "size":
                    value = bytes_to_human_readable(int(value))
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

    def handle_action(self, action_id, control_id=None):
        self.position = self.display_list.getSelectedPosition()

        if action_id == 117:
            selected_source = self.sources[self.position]
            type = selected_source["type"]
            if type == "Torrent":
                response = xbmcgui.Dialog().contextmenu(["Download to Debrid", "Download to Transmission"])
                if response == 0:
                    self._download_into()
                elif response == 1:
                    kodilog("Selected source: %s" % selected_source)

                    enabled = get_setting("transmission_enabled")
                    url = get_setting("transmission_url")
                    username = get_setting("transmission_user")
                    password = get_setting("transmission_pass")
                    
                    if not enabled or not url:
                        notification("Transmission not configured")
                        return
    
                    infoHash = selected_source.get("infoHash")
                    
                    if not infoHash:
                        notification("No infoHash found")
                        
                    try:
                        queue_torrent_to_transmission(infoHash, url, username, password)
                        notification("Torrent queued to Transmission")
                    except Exception as e:
                        notification(f"Failed to queue torrent to transmission: {e}")
                    return
                        
            elif type == "Direct":
                pass
            else:
                response = xbmcgui.Dialog().contextmenu(["Browse into"])
                if response == 0:
                    self._resolve_pack()

        if action_id == 7:
            if control_id == 1000:
                control_list = self.getControl(control_id)
                self.set_cached_focus(control_id, control_list.getSelectedPosition())
                self._resolve_item(pack_select=False)

    def _download_into(self):
        pass

    def _resolve_pack(self):
        pass

    def _resolve_item(self, pack_select):
        self.setProperty("resolving", "true")

        selected_source = self.sources[self.position]

        resolver_window = ResolverWindow(
            "resolver.xml",
            ADDON_PATH,
            source=selected_source,
            previous_window=self,
            item_information=self.item_information,
        )
        resolver_window.doModal(pack_select)
        self.playback_info = resolver_window.playback_info

        del resolver_window
        self.setProperty("instant_close", "true")
        self.close()

    def show_resume_dialog(self, playback_percent):
        try:
            resume_window = ResumeDialog(
                "resume_dialog.xml",
                ADDON_PATH,
                resume_percent=playback_percent,
            )
            resume_window.doModal()
            return resume_window.resume
        finally:
            del resume_window
