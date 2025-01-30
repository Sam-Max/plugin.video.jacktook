import xbmcgui
from lib.gui.base_window import BaseWindow
from lib.gui.resolver_window import ResolverWindow
from lib.gui.resume_window import ResumeDialog
from lib.utils.kodi_utils import ADDON_PATH
from lib.utils.debrid_utils import get_debrid_status
from lib.utils.kodi_utils import bytes_to_human_readable
from lib.utils.utils import (
    extract_publish_date,
    get_colored_languages,
    get_random_color,
)
from lib.api.jacktook.kodi import kodilog
from typing import List


class SourceItem(xbmcgui.ListItem):
    @staticmethod
    def fromSource(source: dict):
        item = SourceItem(label=f"{source['title']}")
        for info in source:
            value = source[info]
            if info == "peers":
                value = value if value else ""
            if info == "publishDate":
                value = extract_publish_date(value)
            if info == "size":
                value = bytes_to_human_readable(int(value)) if value else ""
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
            item.setProperty(info, str(value))
        return item

class Section:
    def __init__(self, title: str, description: str, sources: List[SourceItem]):
        self.title = title
        self.description = description
        self.sources = sources
        self.position = 0
    
    def set_position(self, position: int):
        self.position = position
        
    def get_source(self):
        return self.sources[self.position]
        
class SectionCollection:
    def __init__(self, current_index: int, sections: List[Section]):
        self.sections = sections
        self.current_index = current_index
        
    def get_current_section(self):
        return self.sections[self.current_index]
    
    def get_current_description(self):
        return self.get_current_section().description
    
    def get_current_sources(self):
        return self.get_current_section().sources
    
    def get_current_source(self):
        return self.get_current_section().get_current_source()

    def get_current_position(self):
        return self.get_current_section().position

    def set_position(self, position: int):
        self.get_current_section().set_position(position)

    def get_next_section(self):
        self.current_index += 1
        if self.current_index > len(self.sections) - 1:
            self.current_index = len(self.sections) - 1
        return self.sections[self.current_index]
        
    def get_previous_section(self):
        self.current_index -= 1
        if self.current_index < 0:
            self.current_index = 0
        return self.sections[self.current_index]
        
    def get_section_by_index(self, index):
        return self.sections[index]
        
    def get_section_index(self):
        return self.current_index
        
    def set_section_index(self, index):
        self.current_index = index
        
    def get_section_count(self):
        return len(self.sections)
        
    def get_sections(self):
        return self.sections
    
    def get_title(self):
        return self.get_current_section().title

    def get_titles(self):
        return [section.title for section in self.sections]

    
    

class SourceSelectNew(BaseWindow):
    def __init__(
        self, xml_file, location, item_information=None, sources=None, uncached=None
    ):
        super().__init__(xml_file, location, item_information=item_information)

        # get a list different providers that appears in the sources
        providersAndSeeds = [
                        [source["provider"], source["seeders"]]
                        for source in sources
                    ]
        
        # reduce the list to providers and the sum of their seeds
        providers = {}
        for provider, seeds in providersAndSeeds:
            if provider in providers:
                providers[provider] += seeds
            else:
                providers[provider] = seeds
                
        # get a list of providers sorted by the sum of their seeds
        sortedProviders = [x[0] for x in sorted(providers.items(), key=lambda x: x[1], reverse=True)]                
        
        sectionList = []
        sectionList.append(Section(
            "Priority Language",
            "Sources with Spanish audio",
            [SourceItem.fromSource(source) for source in sources if 'es' in source["fullLanguages"]]))
        sectionList.append(Section(
            "Top Seeders",
            "Results with the most seeders",
            [SourceItem.fromSource(source) for source in sources if not 'es' in source["fullLanguages"]])
            )
        for provider in sortedProviders:
            sectionList.append(Section(
                provider,
                f"Filtered sources from {provider} provider",
                [SourceItem.fromSource(source) for source in sources if source["provider"] == provider]))
        
        
        self.sections = SectionCollection(0, sectionList)

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
        self.title = self.getControl(1001)
        self.description = self.getControl(1002)
        self.populate_sources_list()
        self.set_default_focus(self.display_list, 1000, control_list_reset=True)
        super().onInit()

    def doModal(self):
        super().doModal()
        return self.playback_info
        
    def populate_sources_list(self):
        
        # nav bar
        titles = self.sections.get_titles()
        current_index = self.sections.get_section_index()
        
        navitems = titles[:current_index]
        navitems = ["...", navitems[-2], navitems[-1]] if len(navitems) > 2 else navitems

        navitems.append(f"[B][COLOR white]{titles[current_index]}[/COLOR][/B]")
        navitems.extend(titles[current_index + 1:])
    
        self.title.setLabel(" | ".join(navitems))
        
        # description
        self.description.setLabel(self.sections.get_current_description())

        # list
        self.display_list.reset()
        sources = self.sections.get_current_sources()
        self.display_list.addItems(sources)
        self.display_list.selectItem(self.sections.get_current_position())

    def handle_action(self, action_id, control_id=None):
        self.sections.set_position(self.display_list.getSelectedPosition())
        kodilog(f"action_id: {action_id}, control_id: {control_id}")
        if action_id == xbmcgui.ACTION_CONTEXT_MENU:
            selected_source = self.sections.get_current_source()
            type = selected_source["type"]
            if type == "Torrent":
                response = xbmcgui.Dialog().contextmenu(["Download to Debrid"])
                if response == 0:
                    self._download_into()
            elif type == "Direct":
                pass
            else:
                response = xbmcgui.Dialog().contextmenu(["Browse into"])
                if response == 0:
                    self._resolve_pack()
        if control_id == 1000:
            if action_id == xbmcgui.ACTION_SELECT_ITEM:
                if control_id == 1000:
                    control_list = self.getControl(control_id)
                    self.set_cached_focus(control_id, control_list.getSelectedPosition())
                    self._resolve_item(pack_select=False)
            if action_id == xbmcgui.ACTION_MOVE_LEFT:
                self.sections.get_previous_section()
                self.populate_sources_list()
            if action_id == xbmcgui.ACTION_MOVE_RIGHT:
                self.sections.get_next_section()
                self.populate_sources_list()
            
    def _download_into(self):
        pass

    def _resolve_pack(self):
        pass

    def _resolve_item(self, pack_select):
        self.setProperty("resolving", "true")

        selected_source = self.sections.get_current_source()

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
