from datetime import date
from json import dumps as json_dumps
from json import loads
from threading import Thread
from typing import Optional

import xbmc
from xbmc import getCondVisibility as get_visibility
from xbmcgui import Dialog, ListItem
from xbmcplugin import setResolvedUrl

from lib.api.trakt.trakt import TraktAPI, TraktLists
from lib.api.trakt.trakt_utils import is_trakt_auth
from lib.clients.subtitle.utils import get_language_code
from lib.clients.tmdb.utils.utils import get_movie_keywords, tmdb_get
from lib.db.cached import cache
from lib.utils.general.utils import (
    make_listing,
    set_watched_file,
)
from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    PLAYLIST,
    action_url_run,
    build_url,
    clear_property,
    close_all_dialog,
    close_busy_dialog,
    execute_builtin,
    get_property,
    get_setting,
    kodilog,
    notification,
    set_property,
    sleep,
    translation,
)
from lib.utils.player.utils import (
    autoscrape_next_episode,
    get_autoscrape_cache_key,
    get_autoscrape_results_cache_key,
)

AUTOPLAY_CONTEXT_NEXT_EPISODE = 1
total_time_errors = ("0.0", "", 0.0, None)
video_fullscreen_check = "Window.IsActive(fullscreenvideo)"


class JacktookPLayer(xbmc.Player):
    _nextep_queue: list = []

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
        self._is_trakt_scrobble_active = False
        self._playback_was_paused = False

    def run(self, data=None):
        if data is None:
            data = {}
        self.set_constants(data)
        self.clear_playback_properties()
        self.add_external_trakt_scrolling()
        self.mark_watched(data)

        close_busy_dialog()
        kodilog(
            f"[PLAYER] run() started: url_type={'plugin' if self.url.startswith('plugin://') else 'direct'}, "
            f"mode={data.get('mode')}, url_start={self.url[:80]}"
        )

        try:
            self.list_item = make_listing(data)
            self.PLAYLIST.add(self.url, self.list_item)
            self.play_video(self.list_item)
        except Exception as e:
            self.run_error(e)

        had_nextep = self._drain_nextep_queue()
        kodilog(f"[PLAYER] _drain_nextep_queue returned had_nextep={had_nextep}")
        kodilog(f"[PLAYER] run() completed")

    def _drain_nextep_queue(self) -> bool:
        """Process queued next episodes after current video has stopped"""
        from lib.utils.kodi.settings import auto_play_enabled as _auto_play_enabled

        if not JacktookPLayer._nextep_queue:
            return False

        while JacktookPLayer._nextep_queue:
            entry = JacktookPLayer._nextep_queue.pop(0)
            data = entry.get("data", {})
            results = entry.get("results")
            kodilog(
                f"[PLAYNEXT] _drain_nextep_queue: "
                f"title={data.get('title', '')}, "
                f"has_results={results is not None}, "
                f"queue_remaining={len(JacktookPLayer._nextep_queue)}"
            )

            if _auto_play_enabled() or results is None:
                # Autoplay or resolved data: play directly (video is already stopped)
                player = JacktookPLayer()
                player.run(data=data)
                del player
            else:
                # Manual: show source select (safe context — no video playing)
                from lib.search import show_source_select as _show_source_select
                resolved = _show_source_select(
                    results,
                    mode=data.get("mode", "tv"),
                    ids=data.get("ids", {}),
                    tv_data=data.get("tv_data", {}),
                    query=data.get("query", ""),
                    media_type=data.get("media_type", ""),
                    rescrape=False,
                    direct=False,
                    autoplay_context=str(AUTOPLAY_CONTEXT_NEXT_EPISODE),
                )
                kodilog(f"[PLAYNEXT] source_select returned resolved={resolved}")
                if not resolved:
                    kodilog("[PLAYNEXT] source_select cancelled; cleanup only")
                    close_busy_dialog()
                    close_all_dialog()
                    clear_property("jacktook_next_dialog_action")
                    try:
                        self.PLAYLIST.clear()
                    except Exception as e:
                        kodilog(f"[PLAYNEXT] failed clearing playlist after cancel: {e}")

        return True

    def play_video(self, list_item):
        close_busy_dialog()

        if not self._check_volume():
            self.cancel_playback()
            return

        try:
            self._handle_trakt_scrobble(list_item)
            self.handle_subtitles(list_item)
            # Signal Kodi that the plugin action is a playback (required to
            # avoid spinners when run() returns after video stops).
            setResolvedUrl(ADDON_HANDLE, True, list_item)
            # For external addon URLs (plugin://, e.g. Jacktorr/Elementum/
            # Torrest), setResolvedUrl already handles playback by invoking
            # the external addon via Kodi's plugin protocol.  Calling
            # Player().play() on top of that triggers a second concurrent
            # busy dialog, crashing Kodi with "Logic error due to two
            # concurrent busydialogs".
            is_plugin = self.url.startswith("plugin://")
            kodilog(
                f"[PLAYER] play_video: is_plugin={is_plugin}, "
                f"calling {'setResolvedUrl only' if is_plugin else 'setResolvedUrl + Player().play()'}"
            )
            if not is_plugin:
                self.play(self.url, list_item)
            self.monitor()
            kodilog("[PLAYER] play_video: monitor() returned")
        except Exception as e:
            kodilog(f"Error during play_video: {e}")
            self.run_error(e)

    def _check_volume(self):
        try:
            if not get_setting("volume_check_enabled") or get_visibility("Player.Muted"):
                return True

            threshold = int(get_setting("volume_check_threshold", 50))

            request = {
                "jsonrpc": "2.0",
                "method": "Application.GetProperties",
                "params": {"properties": ["volume"]},
                "id": 1,
            }
            json_query = xbmc.executeJSONRPC(json_dumps(request))
            response = loads(json_query)

            volume = response.get("result", {}).get("volume", 0)
            if volume > threshold:
                execute_builtin(f"SetVolume({threshold})")
                notification(
                    translation(90221) % threshold,
                    heading=translation(90220),
                    time=3000,
                )

            return True
        except Exception as e:
            kodilog(f"Error checking volume: {e}")
            return True

    def _handle_trakt_scrobble(self, list_item):
        if is_trakt_auth() and get_setting("trakt_scrobbling_enabled") and self.data.get("ids"):
            last_position = TraktAPI().scrobble.trakt_get_last_tracked_position(self.data)
            if last_position > 0:
                list_item.setProperty("StartPercent", str(last_position))
            TraktAPI().scrobble.trakt_start_scrobble(self.data)
            self._is_trakt_scrobble_active = True

    def _is_trakt_scrobble_enabled(self):
        return (
            self._is_trakt_scrobble_active
            and is_trakt_auth()
            and get_setting("trakt_scrobbling_enabled")
            and self.data.get("ids")
        )

    def handle_trakt_pause_resume(self):
        is_paused = bool(get_visibility("Player.Paused"))

        if not self._is_trakt_scrobble_enabled():
            self._playback_was_paused = is_paused
            return

        if is_paused and not self._playback_was_paused:
            TraktAPI().scrobble.trakt_pause_scrobble(self.data)
        elif self._playback_was_paused and not is_paused:
            TraktAPI().scrobble.trakt_start_scrobble(self.data)

        self._playback_was_paused = is_paused

    def monitor(self):
        ensure_dialog_closed = False
        kodilog("[PLAYER] monitor() entered")

        try:
            while not self.isPlayingVideo():
                if self.kodi_monitor.abortRequested():
                    kodilog("[PLAYER] monitor: abort requested while waiting for video to start")
                    return
                if get_visibility("Window.IsTopMost(okdialog)"):
                    execute_builtin("SendClick(okdialog, 11)")
                    return
                sleep(100)
            kodilog("[PLAYER] monitor: video started playing, entering main loop")

            # Once playing, initialize streams and subtitles
            self.select_audio_stream()
            self.handle_subtitle_selection()
            self.handle_playback_start()

            # Fetch IntroDB segments in background if enabled
            if self.skip_intro_enabled and self.data.get("mode") == "tv":
                introdb_thread = Thread(target=self.fetch_introdb_segments)
                introdb_thread.daemon = True
                introdb_thread.start()

            # Fetch stinger info in background if enabled
            if get_setting("stinger_notifications_enabled") and self.data.get("mode") == "movies":
                stinger_thread = Thread(target=self.fetch_stinger_info)
                stinger_thread.daemon = True
                stinger_thread.start()

            # Monitor loop
            while self.isPlayingVideo():
                self.update_playback_progress()
                self.handle_trakt_pause_resume()
                self.check_autoscrape_threshold()

                if not ensure_dialog_closed:
                    ensure_dialog_closed = True
                    self.playback_close_dialogs()

                self.check_next_dialog()
                self.check_skip_intro()
                self.check_stinger_notification()

                # Handle pending next-episode action from dialog
                if get_property("jacktook_next_dialog_action") == "next_episode":
                    self._handle_next_dialog_action()

                sleep(1000)

            self.handle_playback_stop()
            kodilog("[PLAYER] monitor: main loop exited, handle_playback_stop completed")

        except Exception:
            self.kill_dialog()
        finally:
            kodilog("[PLAYER] monitor: finally block - clearing playback properties")
            self.clear_playback_properties()
        kodilog("[PLAYER] monitor: exiting")

    def handle_subtitles(self, list_item):
        # Skip subtitle handling during autoplay (Play Next) — no dialogs
        if self.data.get("autoplay"):
            kodilog("Autoplay mode: skipping subtitle handling")
            return

        self.subtitles_found = False
        subtitles_path = self.data.get("subtitles_path", [])
        if subtitles_path or get_property("search_subtitles"):
            list_item.setSubtitles(subtitles_path)
            self.setSubtitleStream(0)
            self.subtitles_found = True
        elif get_setting("stremio_subtitle_enabled"):
            try:
                from lib.clients.subtitle.submanager import SubtitleManager

                auto_select = get_setting("auto_subtitle_selection", False)
                subtitle_manager = SubtitleManager(self.data, self.notification)
                subs_paths = subtitle_manager.fetch_subtitles(auto_select=auto_select)
                if not subs_paths:
                    kodilog("No subtitles found, skipping subtitle loading")
                    self.subtitles_found = False
                    return
                list_item.setSubtitles(subs_paths)
                self.setSubtitleStream(0)
                self.subtitles_found = True
            except Exception as e:
                kodilog(f"Error loading subtitles: {e}")
                self.subtitles_found = False
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
        search_subtitles = get_property("search_subtitles")
        if self.subtitles_found or stremio_subtitle_enabled or search_subtitles:
            self.showSubtitles(True)
            if self.subtitles_found:
                self.notification(translation(90257), time=2000)
                clear_property("search_subtitles")

                # Auto-select subtitle by language if enabled (runs BEFORE return)
                if auto_select_enabled:
                    _, _, subtitles = self.get_player_streams()
                    kodilog(f"Available subtitles: {subtitles}", level=xbmc.LOGDEBUG)
                    for sub in subtitles:
                        if self.lang_code == sub.get("language") and sub.get("isforced") is False:
                            self.setSubtitleStream(sub["index"])
                            self.showSubtitles(True)
                            break

            return

        if auto_select_enabled:
            _, _, subtitles = self.get_player_streams()
            kodilog(f"Available subtitles: {subtitles}", level=xbmc.LOGDEBUG)
            for sub in subtitles:
                if self.lang_code == sub.get("language") and sub.get("isforced") is False:
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
        if auto_audio_enabled and auto_audio_language and auto_audio_language.lower() != "none":
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
            if (
                self.getTotalTime() not in total_time_errors
                and get_visibility(video_fullscreen_check)
                and self.on_started
            ):
                self.on_started()
        except Exception as e:
            kodilog(f"Error in handle_playback_start: {e}")

    def update_playback_progress(self):
        try:
            self.total_time = self.getTotalTime()
            self.current_time = self.getTime()
            if self.total_time and self.total_time > 0:
                self.watched_percentage = round(float(self.current_time / self.total_time * 100), 1)
                self.data["progress"] = self.watched_percentage
                self.data["current_time"] = self.current_time
                self.data["total_time"] = self.total_time
        except Exception as e:
            kodilog(f"Error updating playback progress: {e}")

    def check_autoscrape_threshold(self):
        try:
            if not getattr(self, "total_time", None) or self.total_time < 60:
                return
            if not getattr(self, "current_time", None):
                return
            if getattr(self, "autoscrape_started", False) is not False:
                return
            if not get_setting("autoscrape_next_episode", False):
                return
            if self.data.get("mode") != "tv":
                return

            threshold = int(get_setting("autoscrape_threshold", 70))
            if self.current_time >= (self.total_time * threshold / 100):
                self.autoscrape_started = True
                next_tv_data = self._get_next_episode_data()
                if not next_tv_data:
                    return
                thread = Thread(target=autoscrape_next_episode, args=(self.data, next_tv_data))
                thread.daemon = True
                thread.start()
        except Exception as e:
            kodilog(f"Error in check_autoscrape_threshold: {e}")

    def check_next_dialog(self):
        try:
            # Skip dialog entirely during autoplay (Play Next chain) — no interruptions
            if self.data.get("autoplay"):
                return

            # Only show PlayNext for TV series, never for movies
            if self.data.get("mode") != "tv":
                return

            if not getattr(self, "total_time", None) or self.total_time < 60:
                return
            if not getattr(self, "current_time", None):
                return
            if not getattr(self, "playback_started_properly", False):
                if self.current_time < 10:
                    self.playback_started_properly = True
                else:
                    return
            if self.current_time < (self.total_time * 0.5):
                return

            use_percentage = get_setting("playnext_use_percentage", False)
            if use_percentage:
                percentage = int(get_setting("playnext_percentage", 95))
                if self.next_dialog and self.watched_percentage >= percentage:
                    self._open_next_dialog()
            else:
                time_left = int(self.total_time) - int(self.current_time)
                if self.next_dialog and time_left <= self.playing_next_time:
                    self._open_next_dialog()
        except Exception as e:
            kodilog(f"Error in check_next_dialog: {e}")

    def _open_next_dialog(self):
        """Open PlayNext with one resolved next episode payload."""
        try:
            next_tv_data = self._get_next_episode_data()
        except Exception as e:
            kodilog(f"[PLAYNEXT] Failed resolving next_tv_data for dialog: {e}")
            next_tv_data = None
        item_info = dict(self.data)
        if self._is_valid_next_tv_data(next_tv_data):
            self.data["next_tv_data"] = next_tv_data
            item_info["next_tv_data"] = next_tv_data
        xbmc.executebuiltin(action_url_run(name="run_next_dialog", item_info=item_info))
        self.next_dialog = False

    def _is_valid_next_tv_data(self, next_tv_data) -> bool:
        """Return True when next_tv_data identifies a positive non-current episode."""
        if not isinstance(next_tv_data, dict):
            return False
        try:
            season = int(next_tv_data.get("season"))
            episode = int(next_tv_data.get("episode"))
        except (TypeError, ValueError):
            return False
        if season <= 0 or episode <= 0:
            return False

        current_tv_data = self.data.get("tv_data") or {}
        try:
            current_season = int(current_tv_data.get("season"))
            current_episode = int(current_tv_data.get("episode"))
        except (TypeError, ValueError):
            return True
        return (season, episode) != (current_season, current_episode)

    def _authoritative_next_tv_data(self):
        """Prefer dialog/player next_tv_data, falling back to recalculation."""
        next_tv_data = self.data.get("next_tv_data")
        if self._is_valid_next_tv_data(next_tv_data):
            kodilog(f"[PLAYNEXT] Using authoritative next_tv_data {next_tv_data}")
            return next_tv_data

        next_tv_data = self._get_next_episode_data()
        kodilog(f"[PLAYNEXT] _get_next_episode_data returned {next_tv_data}")
        if self._is_valid_next_tv_data(next_tv_data):
            self.data["next_tv_data"] = next_tv_data
            return next_tv_data
        return None

    def _check_still_watching_threshold(self) -> bool:
        """Check consecutive autoplay count and prompt 'Still Watching?' dialog.

        Returns True if the user stopped (caller should abort), False to continue.
        """
        threshold = int(get_setting("playnext_threshold", 0))
        if threshold <= 0:
            return False

        count_str = get_property("jacktook_consecutive_autoplays")
        try:
            count = int(count_str) if count_str else 1
        except (ValueError, TypeError):
            count = 1

        if count >= threshold:
            from xbmcgui import Dialog

            confirmed = Dialog().yesno(
                "Still watching?",
                "You've watched several episodes in a row. Continue?",
                yeslabel="Continue",
                nolabel="Stop",
            )
            if not confirmed:
                clear_property("jacktook_consecutive_autoplays")
                clear_property("jacktook_next_dialog_action")
                return True
            count = 1
        else:
            count += 1

        set_property("jacktook_consecutive_autoplays", str(count))
        return False

    def _queue_from_autoscrape_cache(self, next_tv_data: dict, ids: dict) -> bool:
        """Check autoscrape cache and if hit, queue next episode + STOP player."""
        id_value = ids.get("original_id") or ids.get("imdb_id") or ids.get("tmdb_id")
        if id_value is None:
            return False

        cache_key = get_autoscrape_cache_key(
            id_value, next_tv_data.get("season"), next_tv_data.get("episode")
        )
        cached_data = cache.get(cache_key)
        if not cached_data:
            kodilog(f"[PLAYNEXT] Autoscrape cache MISS for key={cache_key}")
            return False

        kodilog(f"[PLAYNEXT] Autoscrape cache HIT for key={cache_key}")
        from lib.utils.kodi.settings import auto_play_enabled

        if auto_play_enabled():
            entry_data = dict(cached_data)
            entry_data["autoplay"] = True
            entry_data["playnext_context"] = True
            JacktookPLayer._nextep_queue.append({"data": entry_data})
            kodilog("[PLAYNEXT] Queued autoplay from cache, stopping player")
            self.stop()
            clear_property("jacktook_next_dialog_action")
            return True

        # Autoplay disabled: queue cached raw results for source select
        results_cache_key = get_autoscrape_results_cache_key(
            id_value, next_tv_data.get("season"), next_tv_data.get("episode")
        )
        cached_results = cache.get(results_cache_key)

        entry_data = {
            "mode": self.data.get("mode", "tv"),
            "ids": ids,
            "tv_data": next_tv_data,
            "return_tv_data": self.data.get("tv_data", {}),
            "query": self.data.get("title", ""),
            "media_type": self.data.get("media_type", ""),
            "playnext_context": True,
        }
        JacktookPLayer._nextep_queue.append({
            "data": entry_data,
            "results": cached_results,
        })
        kodilog(
            f"[PLAYNEXT] Queued source select from cache"
            f" (results: {len(cached_results) if cached_results else 0}),"
            f" stopping player"
        )
        self.stop()
        clear_property("jacktook_next_dialog_action")
        return True

    def _handle_next_dialog_action(self):
        """Handle PlayNext using the dialog's logical next episode as authority.

        Kodi's PLAYLIST may still exist for playback mechanics, but it must not
        decide the PlayNext target here: a stale playlist item can drift from
        the `next_tv_data` shown by the dialog. Resolve the logical next episode
        first, then queue it from cache or via the silent background search.
        """

        from json import dumps as json_dumps

        kodilog(
            f"[PLAYNEXT] _handle_next_dialog_action:"
            f" tv_data={self.data.get('tv_data')},"
            f" ids={self.data.get('ids')}"
        )

        if self._check_still_watching_threshold():
            return

        next_tv_data = self._authoritative_next_tv_data()
        if not next_tv_data:
            clear_property("jacktook_next_dialog_action")
            return

        ids = self.data.get("ids", {})

        # Prefer the logical PlayNext queue paths over Kodi PLAYLIST advance.
        # PLAYLIST fallback is intentionally not consulted before next_tv_data.
        if self._queue_from_autoscrape_cache(next_tv_data, ids):
            return  # Cache hit → queued → player.stop() called

        # No cache: fire silent background search thread for the same target.
        kodilog("[PLAYNEXT] No cache, firing silent background search")
        item_data = {
            "ids": ids,
            "title": self.data.get("title", ""),
            "mode": self.data.get("mode", ""),
            "media_type": self.data.get("media_type", ""),
        }
        Thread(target=self._background_search_and_queue, args=(item_data, next_tv_data)).start()
        clear_property("jacktook_next_dialog_action")

    def _background_search_and_queue(self, item_data: dict, next_tv_data: dict) -> None:
        """Search silently in background, queue result, then stop player"""
        from lib.utils.player.utils import autoscrape_next_episode

        try:
            kodilog("[PLAYNEXT] Background search starting (silent)")
            autoscrape_next_episode(item_data, next_tv_data)
            kodilog("[PLAYNEXT] Background search complete, checking cache")

            ids = item_data.get("ids", {})
            # Check cache again — autoscrape_next_episode populates it
            self._queue_from_autoscrape_cache(next_tv_data, ids)
        except Exception as e:
            kodilog(f"[PLAYNEXT] Background search error: {e}")

    def _validate_next_episode_inputs(self):
        """Validate that we have the data needed to find the next episode.

        Returns (tmdb_id, season, episode) or None.
        """
        if self.data.get("mode") != "tv":
            return None

        ids = self.data.get("ids") or {}
        tmdb_id = ids.get("tmdb_id")
        if not tmdb_id:
            return None

        tv_data = self.data.get("tv_data") or {}
        season = tv_data.get("season")
        episode = tv_data.get("episode")
        if season is None or episode is None:
            return None

        try:
            season = int(season)
            episode = int(episode)
        except (TypeError, ValueError):
            return None

        return tmdb_id, season, episode

    def _fetch_season_episodes(self, tmdb_id: str, season: int) -> Optional[list]:
        """Fetch episode list for a given season from TMDB. Returns list or None."""
        season_details = tmdb_get("season_details", {"id": tmdb_id, "season": season})
        if not season_details or not hasattr(season_details, "episodes"):
            return None
        episodes = getattr(season_details, "episodes", [])
        return episodes or None

    def _advance_across_season_boundary(
        self, tmdb_id: str, season: int, episode: int, episodes: list, tv_details
    ) -> Optional[tuple]:
        """Calculate the next episode position, crossing season boundary if needed.

        Returns (next_season, next_episode, search_episodes) or None if at series end.
        """
        max_episode = max(
            (getattr(ep, "episode_number", 0) for ep in episodes),
            default=0,
        )

        next_season = season
        next_episode = episode + 1

        if episode < max_episode:
            return next_season, next_episode, episodes

        # Season boundary: advance to next season
        # TMDB's number_of_seasons INCLUDES season 0 (specials), so we count
        # only seasons with season_number > 0 from the seasons list instead.
        all_seasons = getattr(tv_details, "seasons", None)
        if all_seasons:
            real_seasons = {
                s.season_number for s in all_seasons if getattr(s, "season_number", 0) > 0
            }
            max_season = max(real_seasons) if real_seasons else 1
        else:
            max_season = getattr(tv_details, "number_of_seasons", 1) or 1
        if season >= max_season:
            return None

        next_season = season + 1
        next_episode = 1
        next_episodes = self._fetch_season_episodes(tmdb_id, next_season)
        if not next_episodes:
            return None

        return next_season, next_episode, next_episodes

    def _find_next_episode_by_number(self, episodes: list, target_episode: int):
        """Find episode by number, checking air_date is not in the future.

        Returns the episode object or None.
        """
        for ep in episodes:
            if getattr(ep, "episode_number", 0) != target_episode:
                continue
            air_date = getattr(ep, "air_date", None)
            if air_date:
                try:
                    parts = air_date.split("-")
                    ep_date = date(int(parts[0]), int(parts[1]), int(parts[2]))
                    if date.today() < ep_date:
                        return None
                except (ValueError, IndexError):
                    pass
            return ep
        return None

    def _get_next_episode_data(self):
        """Return next_tv_data dict for the next aired episode, or None."""
        kodilog(
            f"[PLAYNEXT] _get_next_episode_data: mode={self.data.get('mode')}, "
            f"tv_data={self.data.get('tv_data')}, ids={self.data.get('ids')}"
        )

        inputs = self._validate_next_episode_inputs()
        if not inputs:
            kodilog("[PLAYNEXT] _get_next_episode_data: missing required inputs, returning None")
            return None
        tmdb_id, season, episode = inputs
        kodilog(
            f"[PLAYNEXT] _get_next_episode_data: tmdb_id={tmdb_id},"
            f" season={season}, episode={episode}"
        )

        tv_details = tmdb_get("tv_details", tmdb_id)
        if not tv_details:
            kodilog("[PLAYNEXT] _get_next_episode_data: tv_details fetch failed, returning None")
            return None

        episodes = self._fetch_season_episodes(tmdb_id, season)
        if not episodes:
            kodilog(
                "[PLAYNEXT] _get_next_episode_data: no episodes found for"
                " current season, returning None"
            )
            return None

        pos = self._advance_across_season_boundary(tmdb_id, season, episode, episodes, tv_details)
        if not pos:
            kodilog(
                "[PLAYNEXT] _get_next_episode_data: at series end or"
                " boundary fetch failed, returning None"
            )
            return None
        next_season, next_episode, search_episodes = pos

        next_ep = self._find_next_episode_by_number(search_episodes, next_episode)
        if not next_ep:
            kodilog(
                "[PLAYNEXT] _get_next_episode_data: next episode not found"
                " or not yet aired, returning None"
            )
            return None

        result = {
            "name": getattr(next_ep, "name", ""),
            "episode": next_episode,
            "season": next_season,
        }
        kodilog(f"[PLAYNEXT] _get_next_episode_data returning: {result}")
        return result

    def handle_playback_stop(self):
        kodilog("[PLAYER] handle_playback_stop entered")
        if self._is_trakt_scrobble_enabled():
            TraktAPI().scrobble.trakt_stop_scrobble(self.data)
            self._is_trakt_scrobble_active = False

        # Persist playback progress
        set_watched_file(self.data)

        close_busy_dialog()
        clear_property("jacktook_next_dialog_action")
        kodilog("[PLAYER] handle_playback_stop completed")

    def build_playlist(self):
        next_tv_data = self._get_next_episode_data()
        kodilog(f"[PLAYNEXT] build_playlist: next_tv_data={next_tv_data}")
        if not next_tv_data:
            return

        ids = self.data.get("ids") or {}
        episode_name = next_tv_data.get("name", "")
        label = f"{next_tv_data.get('season')}x{next_tv_data.get('episode')}. {episode_name}"
        query = self.data.get("title", "")

        if get_setting("autoscrape_next_episode", False):
            url = build_url(
                "play_autoscraped",
                mode=self.data["mode"],
                query=query,
                ids=ids,
                tv_data=next_tv_data,
                preferred_group=self.preferred_group,
                autoplay_context=str(AUTOPLAY_CONTEXT_NEXT_EPISODE),
            )
        else:
            url = build_url(
                "search",
                mode=self.data["mode"],
                query=query,
                ids=ids,
                tv_data=next_tv_data,
                rescrape=True,
                preferred_group=self.preferred_group,
                autoplay_context=str(AUTOPLAY_CONTEXT_NEXT_EPISODE),
                skip_cancel_on_back=True,
            )

        # Deduplication: Check if this URL is already in the playlist
        for i in range(self.PLAYLIST.size()):
            if self.PLAYLIST[i].getPath() == url:
                kodilog(f"[PLAYNEXT] build_playlist: duplicate URL, skipping: {url}")
                return

        kodilog(f"[PLAYNEXT] build_playlist: adding to PLAYLIST label={label}, url={url}")

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
        if not (data.get("playnext_context") or data.get("autoplay")):
            clear_property("jacktook_consecutive_autoplays")
        self.data = data
        self.url = self.data["url"]
        self.watched_percentage = self.data.get("progress", 0.0)
        self.total_time = 0
        self.current_time = 0
        self.playback_started_properly = False
        self.autoscrape_started = False
        self.next_dialog = get_setting("playnext_dialog_enabled")
        self._is_trakt_scrobble_active = False
        self._playback_was_paused = False
        from lib.utils.general.utils import extract_release_group

        self.preferred_group = extract_release_group(self.data.get("title", ""))

        # Skip intro state
        self.skip_intro_enabled = get_setting("skip_intro_enabled")
        self.skip_intro_auto = get_setting("skip_intro_auto")
        self.skip_intro_segments = None
        self.skip_intro_handled = {"intro": False, "recap": False}

        # Stinger notification state
        self.stinger_notified = False
        self.stinger_keywords = []
        self.has_stinger = False

    def fetch_introdb_segments(self):
        """Fetch segment data from IntroDB in a background thread."""
        try:
            ids = self.data.get("ids", {})
            tv_data = self.data.get("tv_data", {})
            imdb_id = ids.get("imdb_id")
            season = tv_data.get("season")
            episode = tv_data.get("episode")

            if not imdb_id or not season or not episode:
                kodilog("Skip intro: Missing IMDb ID, season, or episode")
                return

            from lib.clients.introdb import get_segments

            self.skip_intro_segments = get_segments(imdb_id, season, episode)
            kodilog(f"IntroDB segments: {self.skip_intro_segments}")
        except Exception as e:
            kodilog(f"Error fetching IntroDB segments: {e}")

    def check_skip_intro(self):
        try:
            if not self.skip_intro_enabled or not self.skip_intro_segments:
                return
            if not getattr(self, "current_time", None):
                return

            current_ms = int(self.current_time * 1000)

            for segment_type in ("recap", "intro"):
                if self.skip_intro_handled.get(segment_type):
                    continue

                segment = self.skip_intro_segments.get(segment_type)
                if not segment:
                    continue

                start_ms = segment.get("start_ms", 0)
                end_ms = segment.get("end_ms", 0)
                end_sec = segment.get("end_sec", end_ms / 1000)

                if start_ms <= current_ms <= end_ms:
                    self.skip_intro_handled[segment_type] = True

                    if self.skip_intro_auto:
                        self.seekTime(end_sec)
                    else:
                        label = "Skip Intro" if segment_type == "intro" else "Skip Recap"
                        xbmc.executebuiltin(
                            action_url_run(
                                name="run_skip_intro_dialog",
                                segment_data=json_dumps(segment),
                                skip_label=label,
                            )
                        )
                elif current_ms > end_ms:
                    self.skip_intro_handled[segment_type] = True
        except Exception as e:
            kodilog(f"Error in check_skip_intro: {e}")

    def fetch_stinger_info(self):
        """Fetch stinger keywords from TMDB in a background thread."""
        try:
            if not get_setting("stinger_notifications_enabled"):
                return
            if self.data.get("mode") != "movies":
                return

            ids = self.data.get("ids", {})
            tmdb_id = ids.get("tmdb_id")
            if not tmdb_id:
                kodilog("Stinger: Missing TMDB ID")
                return

            self.stinger_keywords = get_movie_keywords(tmdb_id)
            self.has_stinger = any(
                k.lower() in ("aftercreditsstinger", "duringcreditsstinger")
                for k in self.stinger_keywords
            )
            kodilog(f"Stinger keywords: {self.stinger_keywords}, has_stinger: {self.has_stinger}")
        except Exception as e:
            kodilog(f"Error fetching stinger info: {e}")

    def check_stinger_notification(self):
        try:
            if not get_setting("stinger_notifications_enabled"):
                return
            if not self.has_stinger or self.stinger_notified:
                return
            if not getattr(self, "total_time", None) or self.total_time < 60:
                return
            if not getattr(self, "current_time", None):
                return

            time_left = int(self.total_time) - int(self.current_time)
            stinger_notification_time = int(get_setting("stinger_notification_time", 180))

            if time_left <= stinger_notification_time:
                notification(translation(90183), time=5000)
                self.stinger_notified = True
        except Exception as e:
            kodilog(f"Error in check_stinger_notification: {e}")

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
        activePlayers = '{"jsonrpc": "2.0", "method": "Player.GetActivePlayers", "id": 1}'
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
            translation(90629),
            translation(90630),
            yeslabel=translation(90631),
            nolabel=translation(90242),
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
        kodilog("[PLAYER] cancel_playback called")
        self._cleanup_playback_session()
        try:
            setResolvedUrl(ADDON_HANDLE, False, ListItem(offscreen=True))
        except Exception as e:
            kodilog(
                f"setResolvedUrl failed in cancel_playback (expected when using direct play): {e}"
            )
        self.stop()

    def _cleanup_playback_session(self):
        kodilog("[PLAYER] _cleanup_playback_session: clearing PLAYLIST, closing dialogs")
        self.PLAYLIST.clear()
        close_busy_dialog()
        close_all_dialog()

    def run_error(self, e: Exception):
        notification("Playback Failed", time=3500)
        if self.on_error:
            self.on_error()
        self.cancel_playback()
        self.clear_playback_properties()
