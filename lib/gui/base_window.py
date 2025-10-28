import abc
from copy import deepcopy
import json
from typing import Any, Dict, Tuple
from lib.domain.torrent import TorrentStream
from lib.utils.debrid.debrid_utils import get_magnet_from_uri
from lib.utils.player.utils import resolve_playback_url
from lib.utils.general.utils import Indexer, IndexerType
from lib.utils.kodi.utils import ADDON, kodilog
import xbmcgui


ACTION_PREVIOUS_MENU = 10
ACTION_PLAYER_STOP = 13
ACTION_NAV_BACK = 92


class BaseWindow(xbmcgui.WindowXMLDialog):
    def __init__(self, xml_file, location, item_information=None, previous_window=None):
        super().__init__(xml_file, location)
        self.item_information = {}
        self.previous_window = previous_window
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
            if self.previous_window:
                self.previous_window.setProperty("instant_close", "true")
                self.previous_window.close()
            self.close()
        elif action_id != 7:
            self.handle_action(action_id, self.getFocusId())

    def _ensure_playback_info(self, source: TorrentStream):
        url, magnet, is_torrent = self._extract_source_details(source)
        source_data = self.prepare_source_data(
            source=source,
            url=url,
            magnet=magnet,
            is_torrent=is_torrent,
        )
        return resolve_playback_url(source_data) or {}

    def _extract_source_details(self, source: TorrentStream) -> Tuple[str, str, bool]:
        url = source.url or ""
        guid = source.guid or ""
        magnet = ""
        indexer = source.indexer
        source_type = source.type
        is_torrent = source.type == IndexerType.TORRENT

        if source_type in (IndexerType.DIRECT, IndexerType.STREMIO_DEBRID):
            return url, magnet, is_torrent

        # Prefer magnet in guid
        if guid.startswith("magnet:?"):
            magnet = guid
        # Handle Burst indexer
        elif indexer == Indexer.BURST:
            url = guid
        # Prefer .torrent in guid or url
        elif guid.endswith(".torrent"):
            url = guid
        elif url.endswith(".torrent"):
            pass
        # Try to extract magnet from guid if it's a details page
        elif guid.startswith("http"):
            magnet_candidate, _ = get_magnet_from_uri(guid)
            if magnet_candidate:
                magnet = magnet_candidate

        # Try to extract magnet from url if it's a details page
        if not magnet and url.startswith("http"):
            magnet_candidate, _ = get_magnet_from_uri(url)
            if magnet_candidate:
                magnet = magnet_candidate
            else:
                url = ""

        # --- Fallback: magnet from url ---
        if not magnet and url.startswith("magnet:?"):
            magnet, url = url, ""

        return url, magnet, is_torrent

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
            "type": source.type,
            "debrid_type": source.debridType,
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

    @abc.abstractmethod
    def handle_action(self, action_id, control_id=None):
        pass
