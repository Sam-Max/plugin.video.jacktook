import os
import requests
from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem, endOfDirectory
from resources.lib.kodi import ADDON_PATH, Keyboard, get_setting, log, notify


anilist_client_id = get_setting("anilist_client_id", "14375")
anilist_client_secret = get_setting(
    "anilist_client_secret", "tOJ5CJA9JM2pmJrHM8XaZgnM9XgL7HaLTM3krdML"
)


def get_anime_client():
    return Anime(
        anilist_client_id,
        anilist_client_secret,
    )


def search_anilist(category, page, plugin, func, func2):
    page += 1
    client = get_anime_client()

    if category == "search":
        text = Keyboard(id=30242)
        if text:
            data = client.search(str(text))
        else:
            return

    if category == "Trending":
        data = client.get_trending(page=page, perPage=10)
    elif category == "Popular":
        data = client.get_popular(page=page, perPage=10)

    anilist_show_results(
        data,
        func=func,
        func2=func2,
        category=category,
        page=page,
        plugin=plugin,
    )


def anilist_show_results(results, func, func2, category, page, plugin):
    for res in results:
        if res["title"]["english"]:
            title = res["title"]["english"]
        else:
            title = res["title"]["romaji"]

        id = res["id"]
        description = res["description"]
        coverImage = res["coverImage"]["large"]

        list_item = ListItem(label=title)
        list_item.setArt(
            {
                "poster": coverImage,
                "icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png"),
                "fanart": coverImage,
            }
        )
        info_tag = list_item.getVideoInfoTag()
        info_tag.setMediaType("video")
        info_tag.setTitle(title)
        info_tag.setPlot(description)

        list_item.setProperty("IsPlayable", "false")

        title = title.replace("/", "").replace("?", "")

        addDirectoryItem(
            plugin.handle,
            plugin.url_for(
                func, query=title, mode="anime", id=id, tvdb_id=-1, imdb_id=-1
            ),
            list_item,
            isFolder=True,
        )

    list_item = ListItem(label="Next")
    list_item.setArt(
        {"icon": os.path.join(ADDON_PATH, "resources", "img", "nextpage.png")}
    )
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(func2, category=category, page=page),
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
        query ($query: String) {
            Page {
                media(search: $query, type: ANIME) {
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

SEARCH_ID = """
        query ($id: Int) {
            Media (id: $id, type: ANIME) {
                id
                title {
                    romaji
                    english
                    native
                }
                description
                coverImage {
                    large
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

    def make_request(self, query, variables):
        res = requests.post(
            self.base_url,
            json={"query": query, "variables": variables},
            headers=self.auth,
        )

        if res.status_code == 200:
            media = res.json()["data"]["Page"]["media"]
            return media
        else:
            notify(f"Anilist Error::{res.text}")
            return {}

    def search(self, query):
        variables = {"query": query}
        return self.make_request(SEARCH, variables)

    def get_popular(self, page, perPage):
        variables = {"page": page, "perPage": perPage}
        return self.make_request(POPULARITY, variables)

    def get_trending(self, page, perPage):
        variables = {"page": page, "perPage": perPage}
        return self.make_request(TRENDING, variables)

    def get_by_id(self, id):
        variables = {"id": id}

        res = requests.post(
            self.base_url,
            json={"query": SEARCH_ID, "variables": variables},
            headers=self.auth,
        )

        if res.status_code == 200:
            media = res.json()["data"]["Media"]
            return media
        else:
            notify(f"Anilist Error:{res.text}")
            return {}

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
            notify(f"Anilist Error:{res.text}")
            return ""
