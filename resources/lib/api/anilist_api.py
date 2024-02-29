import requests


class AniList:
    def __init__(self, client_id, client_secret):
        self.base_url = "https://graphql.anilist.co"
        self.auth_url = "https://anilist.co/api/v2/oauth/token"
        _, self.token = self.get_token(client_id, client_secret)
        self.auth = {"Authorization": f"Bearer {self.token}"}

    def make_request(self, query, variables):
        res = requests.post(
            self.base_url,
            json={"query": query, "variables": variables},
            headers=self.auth,
        )

        if res.status_code == 200:
            media = res.json()["data"]["Page"]
            return "sucess", media
        else:
            return f"Anilist error:{res.text}", {}

    def search(self, query, page, perPage=15):
        variables = {
            "query": query, 
            "page": page, 
            "perPage": perPage,
        }
        return self.make_request(SEARCH, variables)

    def get_popular(self, page, perPage):
        variables = {
            "page": page,
            "perPage": perPage,
            "type": "ANIME",
            "sort": "POPULARITY_DESC",
        }
        return self.make_request(BASE_GRAPH, variables)

    def get_trending(self, page, perPage):
        variables = {
            "page": page,
            "perPage": perPage,
            "type": "ANIME",
            "sort": "TRENDING_DESC",
        }
        return self.make_request(BASE_GRAPH, variables)

    def get_by_id(self, id):
        variables = {"id": id}

        res = requests.post(
            self.base_url,
            json={"query": SEARCH_ID, "variables": variables},
            headers=self.auth,
        )

        if res.status_code == 200:
            media = res.json()["data"]["Media"]
            return res.status_code, media
        else:
            error_message = f"Anilist Error:{res.text}"
            return error_message, {}

    def get_token(self, client_id, client_secret):
        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }
        res = requests.post(self.auth_url, data=data)
        if res.status_code == 200:
            return res.status_code, res.json()["access_token"]
        else:
            error_message = f"Anilist Error:{res.text}"
            return error_message, ""


# GraphQL Anilist
BASE_GRAPH = """
    query (
        $page: Int, 
        $perPage: Int, 
        $sort: [MediaSort],
        $format:[MediaFormat],
        $season: MediaSeason,
        $type: MediaType,
        $status: MediaStatus,
        ) {
        Page (page: $page, perPage: $perPage) {
            ANIME: media (
                type: $type, 
                format_in: $format,
                season: $season,
                status: $status,
                sort: $sort
            ) {
                id
                idMal
                title {
                    english
                    romaji
                }
                format
                episodes
                status
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
    query (
        $query: String, 
        $page: Int, 
        $perPage: Int,
        $format:[MediaFormat]
    ) {
        Page (page: $page, perPage: $perPage) {
            ANIME: media (
                search: $query, 
                type: ANIME,
                format_in: $format,
            ) {
                id
                idMal
                format
                title {
                    english
                    romaji
                }
                episodes
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
        Media (
            id: $id, 
            type: ANIME
        ) {
            id
            idMal
            title {
                romaji
                english
                native
            }
            episodes
            description
            coverImage {
                large
            }
        }
    }
    """
