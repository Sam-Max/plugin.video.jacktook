import os
import requests
from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem, endOfDirectory
from resources.lib.kodi import ADDON_PATH, Keyboard, get_setting, notify


def get_anime_client():
    return Anime(
        get_setting("anilist_client_id", "14375"),
        get_setting(
            "anilist_client_secret", "tOJ5CJA9JM2pmJrHM8XaZgnM9XgL7HaLTM3krdML"
        ),
    )


def search_anilist(category, page, plugin, action, next_action):
    page += 1
    client = get_anime_client()

    if category == "search":
        text = Keyboard(id=30242)
        if text:
            results = client.search(str(text))
            anilist_show_results(
                results,
                action=action,
                next_action=next_action,
                category=category,
                page=page,
                plugin=plugin,
            )
        return

    if category == "Trending":
        data = client.get_trending(page=page, perPage=10)
    elif category == "Popular":
        data = client.get_popular(page=page, perPage=10)

    anilist_show_results(
        data,
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
        list_item.setInfo(
            "video",
            {"title": title, "mediatype": "video", "aired": "", "plot": description},
        )
        list_item.setProperty("IsPlayable", "false")

        title = title.replace("/", "")

        addDirectoryItem(
            plugin.handle,
            plugin.url_for(action, query=title, mode="anime", id=id),
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
            notify(f"Error:{res.text}")

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
