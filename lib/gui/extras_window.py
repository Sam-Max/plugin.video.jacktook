import json
import os
import threading
from lib.gui.base_window import BaseWindow
from lib.utils.kodi.utils import (
    ADDON_PATH,
    kodilog,
    execute_builtin,
    notification,
    get_setting,
    build_url,
)
from lib.clients.tmdb.utils.utils import tmdb_get, LANGUAGES
from lib.api.fanart.fanart import get_fanart
from lib.api.imdb.imdb_scraper import get_imdb_trivia, get_imdb_goofs
import xbmcgui
import xbmc


class ExtrasWindow(BaseWindow):
    def __init__(self, xml_file, location, item_information=None, previous_window=None):
        super().__init__(xml_file, location, item_information, previous_window)
        self.tmdb_id = self.item_information.get("tmdb_id")
        self.media_type = self.item_information.get("media_type")  # "movie" or "tv"
        self.imdb_id = self.item_information.get("imdb_id", "")
        self.title = self.item_information.get("title", "")

        # Shared TMDB details data (populated by fetch_details_and_artwork)
        self._tmdb_data = None
        self._details_ready = threading.Event()

        # UI Lists
        self.cast_list_id = 2050
        self.recommended_list_id = 2051
        self.similar_list_id = 2052
        self.ai_similar_list_id = 2053
        self.reviews_list_id = 2054
        self.comments_list_id = 2055
        self.trivia_list_id = 2056
        self.blunders_list_id = 2057
        self.parental_guide_list_id = 2058
        self.trakt_lists_id = 2059
        self.youtube_list_id = 2060
        self.more_year_list_id = 2061
        self.more_genres_list_id = 2062
        self.more_networks_list_id = 2063
        self.collection_list_id = 2064

    def onInit(self):
        super().onInit()
        self._init_properties()
        self.set_button_labels()

        # Start background threads to fetch data so GUI doesn't freeze
        threading.Thread(target=self.fetch_details_and_artwork, daemon=True).start()
        threading.Thread(target=self.fetch_cast, daemon=True).start()
        threading.Thread(target=self.fetch_recommended, daemon=True).start()
        threading.Thread(target=self.fetch_similar, daemon=True).start()
        threading.Thread(target=self.fetch_imdb_data, daemon=True).start()

        # Threads that depend on TMDB details being fetched first
        threading.Thread(target=self._fetch_after_details, daemon=True).start()

        # Set focus to Play button initially
        self.setFocusId(10)

    def _init_properties(self):
        """Initialize all window properties to safe defaults."""
        self.setProperty("title", self.title)
        self.setProperty("clearlogo", "false")
        self.setProperty("fanart", "false")
        self.setProperty("poster", "false")
        self.setProperty("plot_enabled", "false")
        self.setProperty("plot", "")
        self.setProperty("genre", "")
        self.setProperty("tmdb_rating", "false")
        self.setProperty("imdb_rating", "false")
        self.setProperty("metascore_rating", "false")
        self.setProperty("tomatometer_rating", "false")
        self.setProperty("tomatousermeter_rating", "false")
        self.setProperty("display_extra_ratings", "false")
        # Tab system
        self.setProperty("active_tab", "overview")

    def _fetch_after_details(self):
        """Wait for TMDB details fetch, then populate sections that depend on it."""
        self._details_ready.wait(timeout=15)
        if not self._tmdb_data:
            return
        try:
            self._populate_youtube_videos()
        except Exception as e:
            kodilog(f"Error populating YouTube videos: {e}")
        try:
            self._populate_collection()
        except Exception as e:
            kodilog(f"Error populating collection: {e}")
        try:
            self._populate_more_from_year()
        except Exception as e:
            kodilog(f"Error populating more from year: {e}")
        try:
            self._populate_more_from_genres()
        except Exception as e:
            kodilog(f"Error populating more from genres: {e}")
        try:
            self._populate_more_from_networks()
        except Exception as e:
            kodilog(f"Error populating more from networks: {e}")
        try:
            self.fetch_ai_similar()
        except Exception as e:
            kodilog(f"Error populating AI similar: {e}")

    # ─── TMDB Details + Artwork ───────────────────────────────────────────────

    def fetch_details_and_artwork(self):
        try:
            path = "movie_details" if self.media_type == "movie" else "tv_details"
            data = tmdb_get(path, {"id": self.tmdb_id})
            self._tmdb_data = data

            poster = ""
            fanart = ""
            tvdb_id = None

            if data:
                # ── Extract metadata ──
                self._populate_metadata(data)

                # ── Extract images ──
                poster_path = getattr(data, "poster_path", "")
                if poster_path:
                    poster = f"https://image.tmdb.org/t/p/w500{poster_path}"

                backdrop_path = getattr(data, "backdrop_path", "")
                if backdrop_path:
                    fanart = f"https://image.tmdb.org/t/p/original{backdrop_path}"

                if self.media_type != "movie":
                    external_ids = getattr(data, "external_ids", None)
                    if external_ids:
                        tvdb_id = external_ids.get("tvdb_id")
                        if not self.imdb_id:
                            self.imdb_id = external_ids.get("imdb_id", "")
                else:
                    if not self.imdb_id:
                        self.imdb_id = getattr(data, "imdb_id", "") or ""

            # ── Fanart.tv for clearlogo and better backgrounds ──
            language_index = get_setting("language", 18)
            lang = "en"
            try:
                lang = LANGUAGES[int(language_index)].split("-")[0]
            except Exception:
                pass

            media_type_fa = "movies" if self.media_type == "movie" else "tv"
            fa_id = str(self.tmdb_id)
            if self.media_type != "movie" and tvdb_id:
                fa_id = str(tvdb_id)

            fa_data = get_fanart(media_type_fa, lang, fa_id)

            clearlogo = fa_data.get("clearlogo", "")
            if fa_data.get("fanart"):
                fanart = fa_data.get("fanart")
            if fa_data.get("poster"):
                poster = fa_data.get("poster")

            # Set properties if found
            if poster:
                self.setProperty("poster", poster)
            if fanart:
                self.setProperty("fanart", fanart)
            if clearlogo:
                self.setProperty("clearlogo", clearlogo)
            else:
                self.setProperty("clearlogo", "false")

        except Exception as e:
            kodilog(f"Error fetching details/artwork for extras: {e}")
        finally:
            self._details_ready.set()

    def _populate_metadata(self, data):
        """Extract and set genre, plot, rating, year, and runtime from TMDB details."""
        try:
            # Genre
            genres = getattr(data, "genres", None)
            if genres:
                genre_names = []
                for g in genres:
                    name = (
                        g.get("name", "")
                        if hasattr(g, "get")
                        else getattr(g, "name", "")
                    )
                    if name:
                        genre_names.append(name)
                if genre_names:
                    self.setProperty("genre", " / ".join(genre_names))

            # Plot
            overview = getattr(data, "overview", "")
            if overview:
                self.setProperty("plot_enabled", "true")
                self.setProperty("plot", str(overview))

            # Rating (TMDB)
            vote_average = getattr(data, "vote_average", None)
            if vote_average and float(vote_average) > 0:
                self.setProperty("tmdb_rating", "true")
                try:
                    self.getControl(4005).setLabel(f"{float(vote_average):.1f}")
                except Exception:
                    pass

            # Year and runtime — populate Line 2 (control 2001)
            line2_parts = []
            if self.media_type == "movie":
                release_date = getattr(data, "release_date", "")
                if release_date:
                    line2_parts.append(str(release_date)[:4])
                runtime = getattr(data, "runtime", None)
                if runtime:
                    hours = int(runtime) // 60
                    mins = int(runtime) % 60
                    if hours:
                        line2_parts.append(f"{hours}h {mins}m")
                    else:
                        line2_parts.append(f"{mins}m")
            else:
                first_air = getattr(data, "first_air_date", "")
                if first_air:
                    line2_parts.append(str(first_air)[:4])
                num_seasons = getattr(data, "number_of_seasons", None)
                if num_seasons:
                    line2_parts.append(
                        f"{num_seasons} Season{'s' if int(num_seasons) != 1 else ''}"
                    )
                status = getattr(data, "status", "")
                if status:
                    line2_parts.append(str(status))

            if line2_parts:
                try:
                    self.getControl(2001).setLabel("  •  ".join(line2_parts))
                except Exception:
                    pass

            # Vote count / Tagline — populate Line 3 (control 3001)
            tagline = getattr(data, "tagline", "")
            if tagline:
                try:
                    self.getControl(3001).setLabel(f"[I]{tagline}[/I]")
                except Exception:
                    pass

        except Exception as e:
            kodilog(f"Error populating metadata: {e}")

    # ─── Button Labels ────────────────────────────────────────────────────────

    def set_button_labels(self):
        self.setProperty("button10.label", "Play")
        self.setProperty("button11.label", "Trailer")
        self.setProperty("button15.label", "Watchlist")
        self.setProperty("button16.label", "Watched")
        self.setProperty("button17.label", "Refresh")

    # ─── Cast ─────────────────────────────────────────────────────────────────

    def fetch_cast(self):
        if not self.tmdb_id:
            return
        try:
            path = "movie_credits" if self.media_type == "movie" else "tv_credits"
            data = tmdb_get(path, {"id": self.tmdb_id})

            if data and hasattr(data, "cast"):
                castlist = self.getControlList(self.cast_list_id)
                castlist.reset()
                for actor in data.cast[:30]:
                    li = xbmcgui.ListItem(label=actor.get("name", ""))
                    li.setProperty("name", actor.get("name", ""))
                    li.setProperty("role", actor.get("character", ""))
                    li.setProperty("id", str(actor.get("id", "")))

                    profile_path = actor.get("profile_path")
                    if profile_path:
                        thumb = f"https://image.tmdb.org/t/p/w300{profile_path}"
                        li.setArt({"thumb": thumb, "icon": thumb})
                        li.setProperty("thumbnail", thumb)

                    castlist.addItem(li)
                self.setProperty("cast.number", f"({len(data.cast)})")
        except Exception as e:
            kodilog(f"Error fetching cast: {e}")

    # ─── Recommended (2051) ───────────────────────────────────────────────────

    def fetch_recommended(self):
        if not self.tmdb_id:
            return
        try:
            path = (
                "movie_recommendations"
                if self.media_type == "movie"
                else "tv_recommendations"
            )
            data = tmdb_get(path, {"id": self.tmdb_id, "page": 1})
            self.populate_media_list(
                self.recommended_list_id, data, "recommended.number"
            )
        except Exception as e:
            kodilog(f"Error fetching recommended: {e}")

    # ─── Similar / More Like This (2052) ──────────────────────────────────────

    def fetch_similar(self):
        if not self.tmdb_id:
            return
        try:
            path = "movie_similar" if self.media_type == "movie" else "tv_similar"
            data = tmdb_get(path, {"id": self.tmdb_id, "page": 1})
            self.populate_media_list(
                self.similar_list_id, data, "more_like_this.number"
            )
        except Exception as e:
            kodilog(f"Error fetching similar: {e}")

    # ─── AI Similar (2053) — uses recommendations page 2 ─────────────────────

    def fetch_ai_similar(self):
        if not self.tmdb_id:
            return
        path = (
            "movie_recommendations"
            if self.media_type == "movie"
            else "tv_recommendations"
        )
        data = tmdb_get(path, {"id": self.tmdb_id, "page": 2})
        self.populate_media_list(self.ai_similar_list_id, data, "ai_similar.number")

    # ─── Shared media list populator ──────────────────────────────────────────

    def populate_media_list(self, list_id, tmdb_data, count_property):
        if not tmdb_data:
            return
        try:
            items = []
            if hasattr(tmdb_data, "results"):
                items = tmdb_data.results[:20] if tmdb_data.results else []
            elif hasattr(tmdb_data, "_obj_list") and tmdb_data._obj_list:
                items = tmdb_data._obj_list[:20]
            elif isinstance(tmdb_data, list):
                items = tmdb_data[:20]

            if not items:
                return

            media_list = self.getControlList(list_id)
            media_list.reset()

            for item in items:
                title = item.get("title", "") or item.get("name", "")
                li = xbmcgui.ListItem(label=title)
                li.setProperty("name", title)
                li.setProperty("id", str(item.get("id", "")))
                li.setProperty("media_type", item.get("media_type", self.media_type))

                # Extra info for labels in skin
                release = item.get("release_date", "") or item.get("first_air_date", "")
                if release:
                    li.setProperty("release_date", str(release)[:4])
                vote = item.get("vote_average")
                if vote:
                    li.setProperty("vote_average", f"{float(vote):.1f}")

                poster_path = item.get("poster_path")
                if poster_path:
                    thumb = f"https://image.tmdb.org/t/p/w300{poster_path}"
                    li.setArt({"thumb": thumb, "icon": thumb})
                    li.setProperty("thumbnail", thumb)

                media_list.addItem(li)

            self.setProperty(count_property, f"({len(items)})")
        except Exception as e:
            kodilog(f"Error populating media list {list_id}: {e}")

    # ─── YouTube Videos (2060) ────────────────────────────────────────────────

    def _populate_youtube_videos(self):
        data = self._tmdb_data
        if not data:
            return

        videos = getattr(data, "videos", None)
        if not videos:
            return

        results = getattr(videos, "results", None)
        if not results:
            return

        video_items = []
        for v in results:
            site = v.get("site", "")
            if str(site).lower() != "youtube":
                continue
            video_items.append(v)

        if not video_items:
            return

        vid_list = self.getControlList(self.youtube_list_id)
        vid_list.reset()
        for v in video_items[:20]:
            name = v.get("name", "")
            key = v.get("key", "")
            vtype = v.get("type", "")
            li = xbmcgui.ListItem(label=name)
            li.setProperty("name", name)
            li.setProperty("key", key)
            li.setProperty("video_type", vtype)
            thumb = f"https://img.youtube.com/vi/{key}/mqdefault.jpg"
            li.setProperty("thumbnail", thumb)
            li.setArt({"thumb": thumb, "icon": thumb})
            vid_list.addItem(li)

        self.setProperty("youtube_videos.number", f"({len(video_items[:20])})")

    # ─── Collection (2064, movie only) ────────────────────────────────────────

    def _populate_collection(self):
        if self.media_type != "movie":
            return

        data = self._tmdb_data
        if not data:
            return

        collection = getattr(data, "belongs_to_collection", None)
        if not collection:
            return

        collection_id = collection.get("id")
        collection_name = collection.get("name", "")
        collection_poster = collection.get("poster_path", "")

        if not collection_id:
            return

        self.setProperty("more_from_collection.name", collection_name)
        if collection_poster:
            self.setProperty(
                "more_from_collection.poster",
                f"https://image.tmdb.org/t/p/w300{collection_poster}",
            )

        # Fetch collection details
        col_data = tmdb_get("collection_details", collection_id)
        if not col_data:
            return

        parts = getattr(col_data, "parts", None)
        if not parts:
            return

        col_list = self.getControlList(self.collection_list_id)
        col_list.reset()

        count = 0
        for part in parts:
            title = part.get("title", "") or part.get("name", "")
            li = xbmcgui.ListItem(label=title)
            li.setProperty("name", title)
            li.setProperty("id", str(part.get("id", "")))
            li.setProperty("media_type", "movie")

            release = part.get("release_date", "")
            if release:
                li.setProperty("release_date", str(release)[:4])
            vote = part.get("vote_average")
            if vote:
                li.setProperty("vote_average", f"{float(vote):.1f}")

            poster_path = part.get("poster_path")
            if poster_path:
                thumb = f"https://image.tmdb.org/t/p/w300{poster_path}"
                li.setArt({"thumb": thumb, "icon": thumb})
                li.setProperty("thumbnail", thumb)

            col_list.addItem(li)
            count += 1

        self.setProperty("more_from_collection.number", f"({count})")

    # ─── More from Year (2061) ────────────────────────────────────────────────

    def _populate_more_from_year(self):
        data = self._tmdb_data
        if not data:
            return

        if self.media_type == "movie":
            release_date = getattr(data, "release_date", "")
        else:
            release_date = getattr(data, "first_air_date", "")

        if not release_date or len(str(release_date)) < 4:
            return

        year = str(release_date)[:4]

        if self.media_type == "movie":
            discover_data = tmdb_get(
                "discover_movie",
                {
                    "primary_release_year": year,
                    "sort_by": "vote_count.desc",
                    "page": 1,
                },
            )
        else:
            discover_data = tmdb_get(
                "discover_tv",
                {
                    "first_air_date_year": year,
                    "sort_by": "vote_count.desc",
                    "page": 1,
                },
            )

        if discover_data:
            # Filter out the current item
            self._filter_and_populate(
                self.more_year_list_id, discover_data, "more_from_year.number"
            )

    # ─── More from Genres (2062) ──────────────────────────────────────────────

    def _populate_more_from_genres(self):
        data = self._tmdb_data
        if not data:
            return

        genres = getattr(data, "genres", None)
        if not genres:
            return

        genre_ids = []
        for g in genres:
            gid = g.get("id") if hasattr(g, "get") else getattr(g, "id", None)
            if gid:
                genre_ids.append(str(gid))

        if not genre_ids:
            return

        genre_str = ",".join(genre_ids[:3])

        if self.media_type == "movie":
            discover_data = tmdb_get(
                "discover_movie",
                {
                    "with_genres": genre_str,
                    "sort_by": "vote_count.desc",
                    "page": 1,
                },
            )
        else:
            discover_data = tmdb_get(
                "discover_tv",
                {
                    "with_genres": genre_str,
                    "sort_by": "vote_count.desc",
                    "page": 1,
                },
            )

        if discover_data:
            self._filter_and_populate(
                self.more_genres_list_id, discover_data, "more_from_genres.number"
            )

    # ─── More from Networks (2063, TV only) ───────────────────────────────────

    def _populate_more_from_networks(self):
        if self.media_type != "tv":
            return

        data = self._tmdb_data
        if not data:
            return

        networks = getattr(data, "networks", None)
        if not networks:
            return

        network_ids = []
        for n in networks:
            nid = n.get("id") if hasattr(n, "get") else getattr(n, "id", None)
            if nid:
                network_ids.append(str(nid))

        if not network_ids:
            return

        network_str = "|".join(network_ids[:3])

        discover_data = tmdb_get(
            "discover_tv",
            {
                "with_networks": network_str,
                "sort_by": "vote_count.desc",
                "page": 1,
            },
        )

        if discover_data:
            self._filter_and_populate(
                self.more_networks_list_id, discover_data, "more_from_networks.number"
            )

    def _filter_and_populate(self, list_id, tmdb_data, count_property):
        """Populate a media list, filtering out the current item."""
        if not tmdb_data or not hasattr(tmdb_data, "results"):
            return

        results = []
        for item in tmdb_data.results:
            item_id = item.get("id")
            if str(item_id) != str(self.tmdb_id):
                results.append(item)
            if len(results) >= 20:
                break

        if not results:
            return

        media_list = self.getControlList(list_id)
        media_list.reset()

        for item in results:
            title = item.get("title", "") or item.get("name", "")
            li = xbmcgui.ListItem(label=title)
            li.setProperty("name", title)
            li.setProperty("id", str(item.get("id", "")))
            li.setProperty("media_type", item.get("media_type", self.media_type))

            release = item.get("release_date", "") or item.get("first_air_date", "")
            if release:
                li.setProperty("release_date", str(release)[:4])
            vote = item.get("vote_average")
            if vote:
                li.setProperty("vote_average", f"{float(vote):.1f}")

            poster_path = item.get("poster_path")
            if poster_path:
                thumb = f"https://image.tmdb.org/t/p/w300{poster_path}"
                li.setArt({"thumb": thumb, "icon": thumb})
                li.setProperty("thumbnail", thumb)

            media_list.addItem(li)

        self.setProperty(count_property, f"({len(results)})")

    # ─── IMDb/TMDB Reviews, Trivia, Blunders, Comments ────────────────────────

    def fetch_imdb_data(self):
        # Wait up to 5 seconds for fetch_details_and_artwork to set self.imdb_id
        self._details_ready.wait(timeout=5)

        if not self.imdb_id:
            # Still try TMDB reviews and Trakt comments even without IMDb ID
            self._fetch_tmdb_reviews()
            self._fetch_trakt_comments()
            return

        # 1. IMDb Trivia
        try:
            trivia = get_imdb_trivia(self.imdb_id)
            self._populate_text_panel(self.trivia_list_id, trivia, "imdb_trivia.number")
        except Exception as e:
            kodilog(f"Error fetching trivia: {e}")

        # 2. IMDb Goofs
        try:
            goofs = get_imdb_goofs(self.imdb_id)
            self._populate_text_panel(
                self.blunders_list_id, goofs, "imdb_blunders.number"
            )
        except Exception as e:
            kodilog(f"Error fetching goofs: {e}")

        # 3. IMDb Parental Guide
        try:
            from lib.api.imdb.imdb_scraper import get_imdb_parentsguide

            guide = get_imdb_parentsguide(self.imdb_id)
            self._populate_text_panel(
                self.parental_guide_list_id, guide, "imdb_parentsguide.number"
            )
        except Exception as e:
            kodilog(f"Error fetching parental guide: {e}")

        # 4. TMDB Reviews
        self._fetch_tmdb_reviews()

        # 5. Trakt Comments
        self._fetch_trakt_comments()

    def _fetch_tmdb_reviews(self):
        try:
            path = "movie_reviews" if self.media_type == "movie" else "tv_reviews"
            reviews_data = tmdb_get(path, {"id": self.tmdb_id, "page": 1})
            reviews_list = []
            if reviews_data:
                results = None
                if hasattr(reviews_data, "results"):
                    results = reviews_data.results
                elif hasattr(reviews_data, "_obj_list"):
                    results = reviews_data._obj_list

                if results:
                    for rev in results:
                        content = getattr(rev, "content", "") or rev.get("content", "")
                        author = getattr(rev, "author", "") or rev.get(
                            "author", "Unknown"
                        )
                        if content:
                            reviews_list.append(f"[B]{author}[/B]\n{content}")
            self._populate_text_panel(
                self.reviews_list_id, reviews_list, "imdb_reviews.number"
            )
        except Exception as e:
            kodilog(f"Error fetching TMDB reviews: {e}")

    def _fetch_trakt_comments(self):
        try:
            from lib.api.trakt.trakt import TraktAPI

            trakt_comments_data = TraktAPI().lists.trakt_comments(
                self.media_type, self.tmdb_id, sort_type="likes", page_no=1
            )
            comments_list = []
            if isinstance(trakt_comments_data, tuple):
                trakt_comments_data = trakt_comments_data[0]

            if trakt_comments_data and isinstance(trakt_comments_data, list):
                for comment in trakt_comments_data:
                    text = comment.get("comment", "")
                    user = comment.get("user", {}).get("username", "Unknown")
                    if text:
                        comments_list.append(f"[B]{user}[/B]\n{text}")
            self._populate_text_panel(
                self.comments_list_id, comments_list, "trakt_comments.number"
            )
        except Exception as e:
            kodilog(f"Error fetching trakt comments: {e}")
            self._populate_text_panel(
                self.comments_list_id, [], "trakt_comments.number"
            )

    def _populate_text_panel(self, list_id, string_list, count_property):
        try:
            panel = self.getControlList(list_id)
            panel.reset()
            if string_list:
                for text_item in string_list[:20]:
                    li = xbmcgui.ListItem(label="")
                    li.setProperty("text", text_item)
                    panel.addItem(li)
            self.setProperty(count_property, f"({len(string_list)})")
        except Exception as e:
            kodilog(f"Error populating text panel {list_id}: {e}")

    # ─── Action Handling ──────────────────────────────────────────────────────

    def handle_action(self, action_id, control_id=None):
        if action_id == 7:  # Select/Click
            self._handle_click(control_id)

    def _handle_click(self, control_id):
        # Buttons 10-17
        if control_id == 10:  # Play
            mode = "movies" if self.media_type == "movie" else "tv"
            tv_data = self.item_information.get("tv_data", "{}")

            self.close()
            execute_builtin(
                f"PlayMedia({build_url('search', query=self.title, mode=mode, ids=json.dumps({'tmdb_id': self.tmdb_id, 'imdb_id': self.imdb_id}), tv_data=tv_data)})"
            )

        elif control_id == 11:  # Trailer
            execute_builtin(
                f'RunPlugin(plugin://plugin.video.youtube/play/?video_id=search="{self.title} Trailer")'
            )

        elif control_id == 15:  # Watchlist
            try:
                from lib.api.trakt.trakt import TraktAPI

                TraktAPI().lists.add_to_watchlist(
                    self.media_type, {"tmdb": self.tmdb_id}
                )
                notification("Added to Trakt Watchlist")
            except Exception as e:
                kodilog(f"Error modifying trakt watchlist: {e}")
                notification("Error modifying Trakt Watchlist")

        elif control_id == 16:  # Watched
            try:
                from lib.api.trakt.trakt import TraktAPI

                if self.media_type == "movie":
                    TraktAPI().lists.mark_as_watched(
                        "movie", None, None, {"tmdb": self.tmdb_id}
                    )
                else:
                    TraktAPI().lists.mark_as_watched(
                        "show", None, None, {"tmdb": self.tmdb_id}
                    )
                notification("Marked as Watched on Trakt")
            except Exception as e:
                kodilog(f"Error marking watched on trakt: {e}")
                notification("Error modifying Trakt Watched status")

        elif control_id == 17:  # Refresh
            notification("Refreshed Metadata")
            self.close()

        # ── YouTube video click ──
        elif control_id == self.youtube_list_id:
            try:
                item = self.getControlList(self.youtube_list_id).getSelectedItem()
                key = item.getProperty("key")
                if key:
                    execute_builtin(
                        f"RunPlugin(plugin://plugin.video.youtube/play/?video_id={key})"
                    )
            except Exception as e:
                kodilog(f"Error playing YouTube video: {e}")

        # ── Cast click ──
        elif control_id == self.cast_list_id:
            item = self.getControlList(self.cast_list_id).getSelectedItem()
            person_id = item.getProperty("id")
            if person_id:
                from lib.gui.actor_info_window import ActorInfoWindow

                actor_window = ActorInfoWindow(
                    "actor_info.xml",
                    ADDON_PATH,
                    person_id=person_id,
                )
                actor_window.doModal()

        # ── Media list clicks (recommended, similar, ai_similar, collection, more_from_*) ──
        elif control_id in [
            self.recommended_list_id,
            self.similar_list_id,
            self.ai_similar_list_id,
            self.collection_list_id,
            self.more_year_list_id,
            self.more_genres_list_id,
            self.more_networks_list_id,
        ]:
            item = self.getControlList(control_id).getSelectedItem()
            tmdb_id = item.getProperty("id")
            media_type = item.getProperty("media_type")
            title = item.getProperty("name")
            if tmdb_id:
                mode = "movies" if media_type == "movie" else "tv"
                execute_builtin(
                    f"RunPlugin(plugin://plugin.video.jacktook/?action=extras&id={tmdb_id}&media_type={media_type}&title={title})"
                )
                self.close()

        # ── Text list clicks (reviews, comments, trivia, blunders, parental guide) ──
        elif control_id in [
            self.reviews_list_id,
            self.comments_list_id,
            self.trivia_list_id,
            self.blunders_list_id,
            self.parental_guide_list_id,
        ]:
            item = self.getControlList(control_id).getSelectedItem()
            text = item.getProperty("text")
            if text:
                # Remove markdown formatting for the text viewer
                clean_text = (
                    text.replace("[B]", "")
                    .replace("[/B]", "")
                    .replace("[I]", "")
                    .replace("[/I]", "")
                )

                heading = "Information"
                if control_id == self.reviews_list_id:
                    heading = "Review"
                elif control_id == self.comments_list_id:
                    heading = "Comment"
                elif control_id == self.trivia_list_id:
                    heading = "Trivia"
                elif control_id == self.blunders_list_id:
                    heading = "Goof"
                elif control_id == self.parental_guide_list_id:
                    heading = "Parental Guide"

                xbmcgui.Dialog().textviewer(heading, clean_text)
