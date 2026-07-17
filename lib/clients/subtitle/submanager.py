import json
import os
from typing import Any, Dict, List, Optional

import xbmc
import xbmcgui

from lib.clients.subtitle.deepl import DeepLTranslator
from lib.clients.subtitle.opensubstremio import (
    SUBTITLE_EXTENSIONS,
    OpenSubtitleStremioClient,
    safe_subtitle_path_component,
)
from lib.utils.kodi.settings import subtitle_automation_enabled
from lib.utils.kodi.utils import (
    ADDON_PROFILE_PATH,
    get_setting,
    kodilog,
    translation,
)


class KodiJsonRpcClient:
    def json_rpc(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send a JSON-RPC request to Kodi."""
        request_data = {
            "jsonrpc": "2.0",
            "method": method,
            "id": 1,
            "params": params or {},
        }
        response = json.loads(xbmc.executeJSONRPC(json.dumps(request_data)))
        if "error" in response:
            # If you want logging here, you can add a log method or pass a logger
            pass
        return response.get("result", {})


class SubtitleManager(KodiJsonRpcClient):
    def __init__(self, data: Any, notification: Any):
        self.data = data
        self.notification = notification
        self.opensub_client = OpenSubtitleStremioClient(notification)
        self.translator = DeepLTranslator(notification)
        self.last_fetch_status = None

    def convert_language_iso(self, from_value: str) -> str:
        """Convert language to ISO 639-1 format."""
        return xbmc.convertLanguage(from_value, xbmc.ISO_639_1)

    def get_kodi_preferred_subtitle_language(self, iso_format: bool = False) -> str:
        """
        Get the preferred subtitle language from Kodi settings.

        Returns the language in ISO format if iso_format is True.
        """
        subtitle_language = self.json_rpc(
            "Settings.GetSettingValue", {"setting": "locale.subtitlelanguage"}
        )

        value = subtitle_language.get("value", "")
        if value in ["forced_only", "original", "default", "none"]:
            return value
        return self.convert_language_iso(value) if iso_format else value

    def get_downloaded_subtitle_paths(self, folder_path: str) -> List[str]:
        subtitle_files = []
        for root, _, files in os.walk(folder_path):
            for f in files:
                if os.path.splitext(f)[1].lower() in SUBTITLE_EXTENSIONS:
                    subtitle_files.append(os.path.join(root, f))
        return subtitle_files

    def _resolve_addon_manager(self) -> Optional[Any]:
        """Resolve the live Stremio addon catalog (T7 dependency guard).

        Returns the AddonManager instance or ``None`` if resolution fails /
        no addons are available. ``get_subtitles`` treats ``None`` as
        "no catalog available" and short-circuits the external lookup
        gracefully (no crash, falls through to ``not_found``).
        """
        try:
            from lib.clients.stremio.helpers import get_addons

            manager = get_addons()
            if manager is None:
                return None
            if not getattr(manager, "addons", None):
                return None
            return manager
        except Exception as e:
            kodilog(
                f"[StremioSubs] external lookup skipped: no addons resolved and "
                f"none selected ({e})",
                level=xbmc.LOGDEBUG,
            )
            return None

    def fetch_subtitles(
        self,
        auto_select: bool = False,
        folder_path: Optional[str] = None,
        imdb_id: Optional[str] = None,
        title: Optional[str] = None,
    ) -> Optional[List[str]]:
        self.last_fetch_status = None
        title = title or self.data.get("title")
        mode = self.data.get("mode")
        imdb_id = imdb_id or self.data.get("ids", {}).get("imdb_id")
        tv_data = self.data.get("tv_data", {})
        episode = tv_data.get("episode")
        season = tv_data.get("season")

        if not imdb_id:
            kodilog("No IMDb ID found for the current video, skipping subtitles")
            self.last_fetch_status = "no_imdb"
            return None

        if folder_path is None:
            safe_imdb_id = safe_subtitle_path_component(imdb_id)
            folder_path = (
                os.path.join(
                    ADDON_PROFILE_PATH, "Subtitles", safe_imdb_id, str(season), str(episode)
                )
                if mode == "tv"
                else os.path.join(ADDON_PROFILE_PATH, "Subtitles", safe_imdb_id)
            )

        os.makedirs(folder_path, exist_ok=True)

        subtitle_files = self.get_downloaded_subtitle_paths(folder_path)
        if subtitle_files:
            if auto_select or subtitle_automation_enabled():
                return subtitle_files

            dialog = xbmcgui.Dialog()
            use_existing = dialog.yesno(
                translation(90250),
                translation(90251),
                yeslabel=translation(90627),
                nolabel=translation(90628),
            )
            if use_existing:
                return subtitle_files

        stream_subtitles = self.data.get("stream_subtitles") or []
        subtitle_extra_args = {
            "videoHash": self.data.get("videoHash"),
            "videoSize": self.data.get("size"),
            "filename": self.data.get("filename"),
        }
        kodilog(
            f"[StremioSubs] fetch_subtitles received {len(stream_subtitles)} embedded "
            f"subtitle(s) from playback data (auto_select={auto_select})",
            level=xbmc.LOGINFO,
        )
        subtitles = self.opensub_client.select_subtitles(stream_subtitles, auto_select=auto_select)
        selected_embedded_subtitles = bool(subtitles)
        kodilog(
            f"[StremioSubs] embedded selection result: "
            f"selected={len(subtitles) if subtitles else 'none/cancel'}",
            level=xbmc.LOGINFO,
        )
        endpoint_attempted = False
        if not subtitles:
            endpoint_attempted = True
            kodilog(
                "[StremioSubs] no embedded subtitles selected; falling back to "
                "configured OpenSubtitles endpoint",
                level=xbmc.LOGINFO,
            )
            subtitles = self.opensub_client.get_subtitles(
                mode,
                imdb_id,
                season,
                episode,
                auto_select=auto_select,
                addon_manager=self._resolve_addon_manager(),
                extra_args=subtitle_extra_args,
            )
        if subtitles is None:
            self.last_fetch_status = "not_found"
            self.notification(translation(90252))
            return None

        if not subtitles:
            self.last_fetch_status = "not_selected"
            self.notification(translation(90253))
            return None

        subtitle_paths = self.opensub_client.download_subtitles_batch(
            subtitles,
            imdb_id,
            title=title,
            season=season,
            episode=episode,
            folder_path=folder_path,
            auto_select=auto_select,
        )
        kodilog(
            f"[StremioSubs] download step produced {len(subtitle_paths)} "
            f"file(s) (selected_embedded={selected_embedded_subtitles}, "
            f"endpoint_attempted={endpoint_attempted})",
            level=xbmc.LOGINFO,
        )

        if selected_embedded_subtitles and not subtitle_paths and not endpoint_attempted:
            endpoint_attempted = True
            kodilog(
                "[StremioSubs] embedded subtitles were selected but download "
                "yielded 0 files -> retrying via OpenSubtitles endpoint",
                level=xbmc.LOGINFO,
            )
            subtitles = self.opensub_client.get_subtitles(
                mode,
                imdb_id,
                season,
                episode,
                auto_select=auto_select,
                addon_manager=self._resolve_addon_manager(),
                extra_args=subtitle_extra_args,
            )
            if subtitles is None:
                self.last_fetch_status = "not_found"
                self.notification(translation(90252))
                return None
            if not subtitles:
                self.last_fetch_status = "not_selected"
                self.notification(translation(90253))
                return None
            if subtitles:
                subtitle_paths = self.opensub_client.download_subtitles_batch(
                    subtitles,
                    imdb_id,
                    title=title,
                    season=season,
                    episode=episode,
                    folder_path=folder_path,
                    auto_select=auto_select,
                )

        if get_setting("deepl_enabled"):
            if auto_select:
                kodilog("Skipping DeepL subtitle translation during auto-select")
                return subtitle_paths

            dialog = xbmcgui.Dialog()
            yes = dialog.yesno(
                translation(90254),
                translation(90255),
            )
            if yes:
                translated_subtitles_paths = self.translator.translate_multiple_subtitles(
                    subtitle_paths, imdb_id, season, episode
                )
                return translated_subtitles_paths or subtitle_paths

        return subtitle_paths
