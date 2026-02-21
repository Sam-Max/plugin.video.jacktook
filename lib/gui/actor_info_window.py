import threading
from lib.gui.base_window import BaseWindow
from lib.utils.kodi.utils import (
    ADDON_PATH,
    kodilog,
    notification,
    execute_builtin,
)
from lib.clients.tmdb.utils.utils import tmdb_get
import xbmcgui


class ActorInfoWindow(BaseWindow):
    def __init__(self, xml_file, location, person_id=None, previous_window=None):
        super().__init__(xml_file, location, previous_window=previous_window)
        self.person_id = person_id
        self.filmography_list_id = 3000

    def onInit(self):
        super().onInit()
        self.setFocusId(self.filmography_list_id)
        threading.Thread(target=self.fetch_person_details, daemon=True).start()
        threading.Thread(target=self.fetch_filmography, daemon=True).start()

    def fetch_person_details(self):
        if not self.person_id:
            return
        try:
            data = tmdb_get("person_details", params=self.person_id)
            if not data:
                kodilog("No person details found")
                return

            name = getattr(data, "name", "")
            biography = getattr(data, "biography", "")
            birthday = getattr(data, "birthday", "") or ""
            deathday = getattr(data, "deathday", "") or ""
            place_of_birth = getattr(data, "place_of_birth", "") or ""
            known_for = getattr(data, "known_for_department", "") or ""
            profile_path = getattr(data, "profile_path", "")

            self.setProperty("name", name)
            self.setProperty("biography", biography or "No biography available.")
            self.setProperty("known_for", known_for)

            # Birthday info line
            birthday_parts = []
            if birthday:
                birthday_parts.append(f"Born: {birthday}")
            if place_of_birth:
                birthday_parts.append(place_of_birth)
            self.setProperty("birthday_info", "  •  ".join(birthday_parts))

            # Deathday
            if deathday:
                self.setProperty("deathday_info", f"Died: {deathday}")

            # Profile photo
            if profile_path:
                photo_url = f"https://image.tmdb.org/t/p/w500{profile_path}"
                self.setProperty("photo", photo_url)

        except Exception as e:
            kodilog(f"Error fetching person details: {e}")

    def fetch_filmography(self):
        if not self.person_id:
            return
        try:
            data = tmdb_get("person_credits", params=self.person_id)
            if not data:
                return

            cast_list = getattr(data, "cast", [])
            if not cast_list:
                return

            # Sort by date (newest first)
            def get_date(c):
                return c.get("release_date") or c.get("first_air_date") or ""

            sorted_credits = sorted(cast_list, key=get_date, reverse=True)

            filmography = self.getControlList(self.filmography_list_id)
            filmography.reset()

            for credit in sorted_credits[:50]:
                title = credit.get("title") or credit.get("name") or ""
                character = credit.get("character", "")
                media_type = credit.get("media_type", "movie")
                tmdb_id = credit.get("id", "")
                poster_path = credit.get("poster_path", "")

                # Extract year
                date_str = get_date(credit)
                year = date_str[:4] if date_str else ""

                li = xbmcgui.ListItem(label=title)
                li.setProperty("role", character)
                li.setProperty("year", year)
                li.setProperty("id", str(tmdb_id))
                li.setProperty("media_type", media_type)

                if poster_path:
                    thumb = f"https://image.tmdb.org/t/p/w300{poster_path}"
                    li.setArt({"thumb": thumb, "icon": thumb})

                filmography.addItem(li)

            self.setProperty("filmography.count", f"({len(sorted_credits)})")
            self.setFocusId(self.filmography_list_id)

        except Exception as e:
            kodilog(f"Error fetching filmography: {e}")

    def handle_action(self, action_id, control_id=None):
        if action_id != 7:
            return

        # Filmography item clicked → open Extras window for that title
        if control_id == self.filmography_list_id:
            item = self.getControlList(self.filmography_list_id).getSelectedItem()
            tmdb_id = item.getProperty("id")
            media_type = item.getProperty("media_type")
            title = item.getLabel()
            if tmdb_id:
                execute_builtin(
                    f"RunPlugin(plugin://plugin.video.jacktook/"
                    f"?action=extras&id={tmdb_id}"
                    f"&media_type={media_type}&title={title})"
                )
                self.close()
