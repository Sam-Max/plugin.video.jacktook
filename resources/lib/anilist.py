import os
import requests
from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem, endOfDirectory
from xbmc import Keyboard
from resources.lib.kodi import ADDON_PATH, get_setting, hide_busy_dialog, notify


def search_anilist(category, page, plugin, action, next_action):
    client_id = get_setting("anilist_client_id", "14375")
    client_secret = get_setting(
        "anilist_client_secret", "tOJ5CJA9JM2pmJrHM8XaZgnM9XgL7HaLTM3krdML"
    )

    anime = Anime(client_id, client_secret)
    page += 1

    if category == "Trending":
        trending = anime.get_trending(page=page, perPage=10)
        anilist_show_results(
            trending,
            action=action,
            next_action=next_action,
            category=category,
            page=page,
            plugin=plugin,
        )
    elif category == "Popular":
        popular = anime.get_popular(page=page, perPage=10)
        anilist_show_results(
            popular,
            action=action,
            next_action=next_action,
            category=category,
            page=page,
            plugin=plugin,
        )
    elif category == "search":
        keyboard = Keyboard("", "Search on AniList:", False)
        keyboard.doModal()
        if keyboard.isConfirmed():
            text = keyboard.getText().strip()
        else:
            hide_busy_dialog()
            return
        results = anime.search(str(text))
        anilist_show_results(
            results,
            action=action,
            next_action=next_action,
            category=category,
            page=page,
            plugin=plugin,
        )


def anilist_show_results(results, action, next_action, category, page, plugin):
    for res in results:
        if res["title"]["english"]:
            title = res["title"]["english"]
        else:
            title = res["title"]["romaji"]

        description = res["description"]
        coverImage = res["coverImage"]["large"]
        backdrop_path = ""

        list_item = ListItem(label=title)
        list_item.setArt(
            {
                "poster": coverImage,
                "icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png"),
                "fanart": backdrop_path,
            }
        )
        list_item.setInfo(
            "video",
            {"title": title, "mediatype": "video", "aired": "", "plot": description},
        )
        list_item.setProperty("IsPlayable", "false")

        addDirectoryItem(
            plugin.handle,
            plugin.url_for(action, query=title, mode="multi", tracker="anime"),
            list_item,
            isFolder=True,
        )

    list_item = ListItem(label="Next")
    list_item.setArt(
        {"icon": os.path.join(ADDON_PATH, "resources", "img", "nextpage.png")}
    )
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(next_action, category=category, page=page),
        list_item,
        isFolder=True,
    )

    endOfDirectory(plugin.handle)


# GraphQL Anilist
TRENDING = """
        query ($page: Int, $perPage: Int) {
            Page (page: $page, perPage: $perPage) {
                    media (type: ANIME, sort: TRENDING_DESC) {
                        id
                        title {
                            english
                            romaji
                        }
                        description
                        startDate {
                        year, month, day
                        }
                        coverImage {
                            large
                        }
                }
            }
        }
        """

POPULARITY = """
        query ($page: Int, $perPage: Int) {
            Page (page: $page, perPage: $perPage) {
                    media (type: ANIME, sort: POPULARITY_DESC) {
                        id
                        title {
                            english
                            romaji
                        }
                        description
                        startDate {
                        year, month, day
                        }
                        coverImage {
                            large
                        }
                }
            }
        }
        """

SEARCH = """
        query ($search: String) {
            Page {
                media(search: $search, type: ANIME) {
                    id
                    title {
                        english
                        romaji
                    }
                    description
                    coverImage {
                        large
                    }
                }
            }
        }
        """


class Anime:
    def __init__(self, client_id, client_secret):
        self.base_url = "https://graphql.anilist.co"
        self.auth_url = "https://anilist.co/api/v2/oauth/token"
        self.token = self.get_token(client_id, client_secret)
        self.auth = {"Authorization": f"Bearer {self.token}"}

    def search(self, query):
        variables = {"search": query}

        res = requests.post(
            self.base_url,
            json={"query": SEARCH, "variables": variables},
            headers=self.auth,
        )

        if res.status_code == 200:
            media = res.json()["data"]["Page"]["media"]
            return media
        else:
            notify(f"Error:{res.text}")

    def get_popular(self, page, perPage):
        variables = {"page": page, "perPage": perPage}

        res = requests.post(
            self.base_url,
            json={"query": POPULARITY, "variables": variables},
            headers=self.auth,
        )

        if res.status_code == 200:
            media = res.json()["data"]["Page"]["media"]
            return media
        else:
            notify(f"Error:{res.text}")

    def get_trending(self, page, perPage):
        variables = {"page": page, "perPage": perPage}

        res = requests.post(
            self.base_url,
            json={"query": TRENDING, "variables": variables},
            headers=self.auth,
        )

        if res.status_code == 200:
            media = res.json()["data"]["Page"]["media"]
            return media
        else:
            notify(f"Error:{res.text}")

    def get_token(self, client_id, client_secret):
        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }

        res = requests.post(self.auth_url, data=data)

        if res.status_code == 200:
            return res.json()["access_token"]
        else:
            notify(f"Error:{res.text}")
