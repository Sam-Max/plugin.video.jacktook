import abc
from copy import deepcopy
import json
from typing import Any, Dict, Tuple
from lib.domain.torrent import TorrentStream
from lib.utils.torrent.resolve_to_magnet import resolve_to_magnet
from lib.utils.general.utils import Indexer, IndexerType
from lib.utils.kodi.utils import ADDON, kodilog
import xbmcgui


ACTION_PREVIOUS_MENU = 10
ACTION_PLAYER_STOP = 13
ACTION_NAV_BACK = 92


class BaseWindow(xbmcgui.WindowXMLDialog):
    def __init__(self, xml_file, location, item_information=None):
        super().__init__(xml_file, location)
        self.item_information = {}
        self.CACHE_KEY = ""
        self._last_focused_control = (None, None)
        self.action_exitkeys_id = {
            ACTION_PREVIOUS_MENU,
            ACTION_PLAYER_STOP,
            ACTION_NAV_BACK,
        }

        if item_information is None:
            return

        self.add_item_information_to_window(item_information)

    def onInit(self):
        pass

    def get_cached_focus(self):
        cached_data = ADDON.getSetting(self.CACHE_KEY)
        if cached_data:
            try:
                return json.loads(cached_data)
            except json.JSONDecodeError:
                return None, None
        return None, None

    def set_cached_focus(self, control_id, item_id):
        cache_data = json.dumps((control_id, item_id))
        ADDON.setSetting(self.CACHE_KEY, cache_data)

    def set_default_focus(
        self, control_list=None, control_id=None, control_list_reset=False
    ):
        try:
            # Retrieve cached focus if available
            control_id, item_id = self.get_cached_focus()
            if control_id and item_id:
                control = self.getControl(control_id)
                if isinstance(control, xbmcgui.ControlList):
                    control.selectItem(int(item_id))
                    self.setFocus(control)
                    return

            if control_list and control_list.size() > 0:
                if control_list_reset:
                    control_list.selectItem(0)
                self.setFocus(control_list)
            elif control_id:
                control = self.getControl(control_id)
                self.setFocus(control)
            else:
                raise ValueError("Neither valid control list nor control ID provided.")
        except (RuntimeError, ValueError) as e:
            kodilog(f"Could not set focus: {e}")
            if control_id:
                self.setFocusId(control_id)

    def getControlList(self, control_id):
        try:
            control = self.getControl(control_id)
        except RuntimeError as e:
            kodilog(f"Control does not exist {control_id}", {e})
            raise ValueError(f"Control with Id {control_id} does not exist")
        
        if not isinstance(control, xbmcgui.ControlList):
            raise AttributeError(
                f"Control with Id {control_id} should be of type ControlList"
            )
        return control

    def add_item_information_to_window(self, item_information):
        self.item_information = deepcopy(item_information)
        for i in self.item_information:
            value = self.item_information[i]
            try:
                self.setProperty(f"info.{i}", str(value))
            except UnicodeEncodeError:
                self.setProperty(f"info.{i}", value)

    def getControlProgress(self, control_id):
        control = self.getControl(control_id)
        if not isinstance(control, xbmcgui.ControlProgress):
            raise AttributeError(
                f"Control with Id {control_id} should be of type ControlProgress"
            )

        return control

    def onClick(self, control_id):
        self.handle_action(7, control_id)

    def onAction(self, action):
        action_id = action.getId()
        if action_id in self.action_exitkeys_id:
            self.close()
            return
        if action_id != 7:  # Enter(7) also fires an onClick event
            self.handle_action(action_id, self.getFocusId())

    def prepare_source_data(
            self,
            source: TorrentStream,
            url: str,
            magnet: str,
            is_torrent: bool,
            pack_select: bool = False,
        ) -> Dict[str, Any]:
            """Prepare the source data dictionary for resolving playback."""
            return {
                "title": source.title,
                "type": source.type,
                "indexer": source.indexer,
                "url": url,
                "magnet": magnet,
                "info_hash": source.infoHash,
                "is_torrent": is_torrent,
                "is_pack": pack_select,
                "mode": self.item_information.get("mode"),
                "ids": self.item_information.get("ids"),
                "tv_data": self.item_information.get("tv_data"),
            }
    
    def _handle_torrent_source(self, source:TorrentStream) -> Tuple[str, str, bool]:
        guid = source.guid
        magnet = ""
        indexer = source.indexer
        url = source.url or ""

        if guid and guid.startswith("magnet:?"):
            magnet = guid
        elif indexer == Indexer.BURST:
            url, magnet = guid, ""

        if url.startswith("magnet:?") and not magnet:
            magnet, url = url, ""

        if not magnet:
            magnet = resolve_to_magnet(url) or ""

        return url, magnet, True

    def get_source_details(self, source:TorrentStream) -> Tuple[str, str, bool]:
        type = source.type
        url, magnet, is_torrent = "", "", False

        if type == IndexerType.TORRENT:
            url, magnet, is_torrent = self._handle_torrent_source(source)
        elif type == IndexerType.DIRECT:
            url, is_torrent = source.url, False
        elif type == IndexerType.STREMIO_DEBRID:
            url, is_torrent = source.url, False

        return url, magnet, is_torrent
    
    @abc.abstractmethod
    def handle_action(self, action_id, control_id=None):
        pass
