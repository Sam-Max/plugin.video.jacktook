from threading import Thread
from lib.api.trakt.trakt_utils import is_trakt_auth
from lib.clients.subtitle.utils import get_language_code
from lib.clients.tmdb.utils.utils import tmdb_get
from lib.api.trakt.trakt import TraktAPI, TraktLists
from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    PLAYLIST,
    action_url_run,
    build_url,
    clear_property,
    close_all_dialog,
    close_busy_dialog,
    execute_builtin,
    get_setting,
    kodilog,
    notification,
    set_property,
    sleep,
)
from lib.utils.general.utils import (
    make_listing,
    set_watched_file,
)
from lib.utils.player.utils import precache_next_episodes

import xbmc
from xbmc import getCondVisibility as get_visibility
from xbmcgui import ListItem, Dialog
from xbmcplugin import setResolvedUrl

from json import dumps as json_dumps, loads

total_time_errors = ("0.0", "", 0.0, None)
video_fullscreen_check = "Window.IsActive(fullscreenvideo)"


class JacktookPLayer(xbmc.Player):
    def __init__(self, on_started=None, on_error=None):
        xbmc.Player.__init__(self)
        self.url = None
        self.playback_percent = 0.0
        self.playing_filename = ""
        self.media_marked = False
        self.cancel_all_playback = False
        self.kodi_monitor = xbmc.Monitor()
        self.next_dialog = get_setting("playnext_dialog_enabled")
        self.playing_next_time = int(get_setting("playnext_time", 50))
        self.PLAYLIST = PLAYLIST
        self.data = {}
        self.notification = notification
        self.lang_code = "en"
        self.subtitles_found = False
        self.on_started = on_started
        self.on_error = on_error

    def run(self, data={}):
        self.set_constants(data)
        self.clear_playback_properties()
        self.add_external_trakt_scrolling()
        self.mark_watched(data)
        
        precaching_thread = Thread(target=precache_next_episodes, args=(self.data,))
        precaching_thread.start()
        
        close_busy_dialog()

        try:
            self.list_item = make_listing(data)
            self.PLAYLIST.add(self.url, self.list_item)
            if self.data["mode"] == "tv":
                self.build_playlist()
            self.play_video(self.list_item)
        except Exception as e:
            self.run_error(e)

    def play_video(self, list_item):
        close_busy_dialog()

        try:
            self._handle_trakt_scrobble(list_item)
            self.handle_subtitles(list_item)
            setResolvedUrl(ADDON_HANDLE, True, list_item)
            self.monitor()
        except Exception as e:
            kodilog(f"Error during play_video: {e}")
            self.run_error(e)

    def _handle_trakt_scrobble(self, list_item):
        if (
            is_trakt_auth()
            and get_setting("trakt_scrobbling_enabled")
            and self.data.get("ids")
        ):
            last_position = TraktAPI().scrobble.trakt_get_last_tracked_position(
                self.data
            )
            if last_position > 0:
                list_item.setProperty("StartPercent", str(last_position))
            TraktAPI().scrobble.trakt_start_scrobble(self.data)

    def monitor(self):
        ensure_dialog_closed = False

        try:
            while not self.isPlayingVideo():
                if self.kodi_monitor.abortRequested():
                    return
                if get_visibility("Window.IsTopMost(okdialog)"):
                    execute_builtin("SendClick(okdialog, 11)")
                    return
                sleep(100)

            # Once playing, initialize streams and subtitles
            self.select_audio_stream()
            self.handle_subtitle_selection()
            self.handle_playback_start()

            # Monitor loop
            while self.isPlayingVideo():
                self.update_playback_progress()

                if not ensure_dialog_closed:
                    ensure_dialog_closed = True
                    self.playback_close_dialogs()

                self.check_next_dialog()
                sleep(1000)

            self.handle_playback_stop()

        except Exception as e:
            self.kill_dialog()
        finally:
            self.cancel_playback()
            self.clear_playback_properties()

    def handle_subtitles(self, list_item):
        self.subtitles_found = False
        if get_setting("search_subtitles"):
            list_item.setSubtitles(self.data.get("subtitles_path", []))
            self.setSubtitleStream(0)
            self.subtitles_found = True
        elif get_setting("stremio_subtitle_enabled"):
            from lib.clients.subtitle.submanager import SubtitleManager

            subtitle_manager = SubtitleManager(self.data, self.notification)
            subs_paths = subtitle_manager.fetch_subtitles(auto_select=True)
            if not subs_paths:
                kodilog("No subtitles found, skipping subtitle loading")
                self.subtitles_found = False
                return
            list_item.setSubtitles(subs_paths)
            self.setSubtitleStream(0)
            self.subtitles_found = True
        elif get_setting("auto_subtitle_selection"):
            sub_language = str(get_setting("subtitle_language"))
            if sub_language and sub_language.lower() != "None":
                self.lang_code = get_language_code(sub_language)
        else:
            kodilog("No subtitle handling method selected, skipping subtitle loading")

    def handle_subtitle_selection(self):
        """
        Handles subtitle activation and selection logic after playback starts.
        """
        auto_select_enabled = get_setting("auto_subtitle_selection")
        stremio_subtitle_enabled = get_setting("stremio_subtitle_enabled")
        search_subtitles = get_setting("search_subtitles")

        if stremio_subtitle_enabled or search_subtitles:
            self.showSubtitles(True)
            if self.subtitles_found:
                self.notification("Subtitles Loaded", time=2000)
                set_property("search_subtitles", "false")
                return

        if auto_select_enabled:
            _, _, subtitles = self.get_player_streams()
            kodilog(f"Available subtitles: {subtitles}", level=xbmc.LOGDEBUG)
            for sub in subtitles:
                if (
                    self.lang_code == sub.get("language")
                    and sub.get("isforced") is False
                ):
                    self.setSubtitleStream(sub["index"])
                    self.showSubtitles(True)
                    break

        elif not (stremio_subtitle_enabled or auto_select_enabled):
            kodilog("Auto subtitle selection disabled")
            self.showSubtitles(False)

    def select_audio_stream(self):
        """
        Handles automatic audio stream selection based on user settings.
        """
        auto_audio_enabled = get_setting("auto_audio")
        auto_audio_language = str(get_setting("auto_audio_language"))
        if (
            auto_audio_enabled
            and auto_audio_language
            and auto_audio_language.lower() != "none"
        ):
            sleep(500)
            audio_streams = self.getAvailableAudioStreams()
            if audio_streams or len(audio_streams) > 0:
                lang_code = get_language_code(auto_audio_language)
                for stream_lang in audio_streams:
                    if stream_lang == lang_code:
                        self.setAudioStream(audio_streams.index(stream_lang))
                        break

    def handle_playback_failure(self):
        self.kill_dialog()
        if self.on_error:
            self.on_error()
        self.stop()

    def handle_playback_start(self):
        try:
            if self.getTotalTime() not in total_time_errors and get_visibility(
                video_fullscreen_check
            ):
                if self.on_started:
                    self.on_started()
        except Exception as e:
            kodilog(f"Error in handle_playback_start: {e}")

    def update_playback_progress(self):
        try:
            self.total_time = self.getTotalTime()
            self.current_time = self.getTime()
            if self.total_time:
                self.watched_percentage = round(
                    float(self.current_time / self.total_time * 100), 1
                )
                self.data["progress"] = self.watched_percentage
        except Exception as e:
            kodilog(f"Error updating playback progress: {e}")

    def check_next_dialog(self):
        try:
            if not self.total_time or self.total_time < 60:
                return
            if not self.current_time or self.current_time < (self.total_time * 0.1):
                # Don't trigger in the first 10% of playback
                return
            time_left = int(self.total_time) - int(self.current_time)
            if self.next_dialog and time_left <= self.playing_next_time:
                kodilog("Triggering next dialog...")
                xbmc.executebuiltin(
                    action_url_run(name="run_next_dialog", item_info=self.data)
                )
                self.next_dialog = False
        except Exception as e:
            kodilog(f"Error in check_next_dialog: {e}")

    def handle_playback_stop(self):
        if (
            is_trakt_auth()
            and get_setting("trakt_scrobbling_enabled")
            and self.data.get("ids")
        ):
            TraktAPI().scrobble.trakt_stop_scrobble(self.data)
        close_busy_dialog()

    def build_playlist(self):
        if self.data.get("mode") != "tv":
            return

        ids = self.data.get("ids")
        if not ids:
            return

        tmdb_id = ids.get("tmdb_id")
        if not tmdb_id:
            return

        details = tmdb_get("tv_details", tmdb_id)
        tv_data = self.data.get("tv_data", {})
        season = tv_data.get("season")
        episode = tv_data.get("episode")

        if season is None or episode is None:
            return

        season_details = tmdb_get("season_details", {"id": tmdb_id, "season": season})

        if not season_details or not hasattr(season_details, "episodes"):
            return

        for e in getattr(season_details, "episodes"):
            episode_name = getattr(e, "name", "")
            episode_number = getattr(e, "episode_number", 0)

            if episode_number <= int(episode):
                continue

            label = f"{season}x{episode_number}. {episode_name}"
            next_tv_data = {
                "name": episode_name,
                "episode": episode_number,
                "season": season,
            }

            url = build_url(
                "search",
                mode=self.data["mode"],
                query=getattr(details, "name", ""),
                ids=ids,
                tv_data=next_tv_data,
                rescrape=True,
            )

            list_item = ListItem(label=label)
            list_item.setPath(url)
            list_item.setProperty("IsPlayable", "true")

            self.PLAYLIST.add(url=url, listitem=list_item)

    def kill_dialog(self):
        close_all_dialog()

    def playback_close_dialogs(self):
        close_all_dialog()

    def set_constants(self, data):
        self.PLAYLIST.clear()
        self.data = data
        self.url = self.data["url"]
        self.watched_percentage = self.data.get("progress", 0.0)
        self.next_dialog = get_setting("playnext_dialog_enabled")

    def clear_playback_properties(self):
        clear_property("script.trakt.ids")

    def add_external_trakt_scrolling(self):
        ids = self.data.get("ids", {})
        mode = self.data.get("mode")
        title = self.data.get("title", "")

        if ids:
            trakt_ids = {
                "tmdb": ids.get("tmdb_id"),
                "imdb": ids.get("imdb_id"),
                "slug": TraktLists().make_trakt_slug(title),
            }
            if mode == "tv":
                trakt_ids["tvdb"] = ids.get("tvdb_id")
            set_property("script.trakt.ids", json_dumps(trakt_ids))

    def get_player_streams(self):
        activePlayers = (
            '{"jsonrpc": "2.0", "method": "Player.GetActivePlayers", "id": 1}'
        )
        json_query = xbmc.executeJSONRPC(activePlayers)
        json_response = loads(json_query)
        if not json_response.get("result"):
            return None, {}, []
        playerid = json_response["result"][0]["playerid"]
        details_query = {
            "jsonrpc": "2.0",
            "method": "Player.GetProperties",
            "params": {
                "properties": ["currentsubtitle", "subtitles"],
                "playerid": playerid,
            },
            "id": 1,
        }
        json_query = xbmc.executeJSONRPC(json_dumps(details_query))
        details = loads(json_query).get("result", {})
        return (
            playerid,
            details.get("currentsubtitle", {}),
            details.get("subtitles", []),
        )

    def ask_user_retry(self):
        dialog = Dialog()
        choice = dialog.yesno(
            "Playback Failed",
            "The video could not be played.\nDo you want to retry?",
            yeslabel="Retry",
            nolabel="Cancel",
        )
        if choice:
            try:
                self.play_video(make_listing(self.data))
            except Exception as e:
                kodilog(f"Retry failed: {e}")
                self.run_error(e)
        else:
            self.cancel_playback()
            notification("Playback Cancelled", time=2000)

    def mark_watched(self, data):
        set_watched_file(data)

    def cancel_playback(self):
        self.PLAYLIST.clear()
        close_busy_dialog()
        close_all_dialog()
        setResolvedUrl(ADDON_HANDLE, False, ListItem(offscreen=True))

    def run_error(self, e: Exception):
        notification("Playback Failed", time=3500)
        if self.on_error:
            self.on_error()
        self.cancel_playback()
        self.clear_playback_properties()
