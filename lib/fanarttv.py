import requests
from lib.utils.kodi import get_setting


def make_session(url="https://"):
    session = requests.Session()
    session.mount(url, requests.adapters.HTTPAdapter(pool_maxsize=100))
    return session


# Some code snippets from nixgates.
base_url = "https://webservice.fanart.tv/v3/%s/%s"
API_KEY = "fa836e1c874ba95ab08a14ee88e05565"
CLIENT_KEY = get_setting("fanarttv_client_id", API_KEY)

seasonart_keys = ("seasonposter", "seasonbanner", "seasonthumb")
blank_image_values = ("00", "", "None")
session = make_session("https://webservice.fanart.tv")


def search_api_fanart_tv(media_type, language, media_id):
    media_type = "movies" if media_type == "movie" else media_type
    query = base_url % (media_type, media_id)
    headers = {"client-key": CLIENT_KEY, "api-key": API_KEY}
    try:
        response = session.get(query, headers=headers, timeout=20)
        art = response.json()
    except:
        art = None
    if art == None or "error_message" in art:
        return None
    art_get = art.get
    if media_type == "movies":
        poster = art_get("movieposter", [])
        fanart = art_get("moviebackground", [])
        clearlogo = art_get("hdmovielogo", []) + art_get("movielogo", [])
        banner = art_get("moviebanner", [])
        clearart = art_get("movieart", []) + art_get("hdmovieclearart", [])
        landscape = art_get("moviethumb", [])
        discart = art_get("moviedisc", [])
        keyart = [i for i in poster if i["lang"] in blank_image_values]
        fanart_data = {
            "poster": parse_art(poster, language),
            "fanart": parse_art(fanart, language),
            "clearlogo": parse_art(clearlogo, language),
            "banner": parse_art(banner, language),
            "clearart": parse_art(clearart, language),
            "landscape": parse_art(landscape, language),
            "discart": parse_art(discart, language),
            "keyart": parse_art(poster, "keyart"),
            "fanart_added": True,
        }
        discart, keyart = [i["url"] for i in discart], [i["url"] for i in keyart]
    else:
        poster = art_get("tvposter", [])
        fanart = art_get("showbackground", [])
        clearlogo = art_get("hdtvlogo", []) + art_get("clearlogo", [])
        banner = art_get("tvbanner", [])
        clearart = art_get("clearart", []) + art_get("hdclearart", [])
        landscape = art_get("tvthumb", [])
        discart, keyart = [], []
        fanart_data = {
            "poster": parse_art(poster, language),
            "fanart": parse_art(fanart, language),
            "clearlogo": parse_art(clearlogo, language),
            "banner": parse_art(banner, language),
            "clearart": parse_art(clearart, language),
            "landscape": parse_art(landscape, language),
            "season_art": parse_season_art(art, language),
            "discart": "",
            "keyart": "",
            "fanart_added": True,
        }
    return fanart_data


def parse_season_art(art, language):
    season_art = {}
    for item in seasonart_keys:
        results = art.get(item, [])
        try:
            seasons = sorted(
                list(
                    set(
                        [
                            i["season"]
                            for i in results
                            if i["season"] != "all"
                            and (
                                len(i["season"]) == 1 or not i["season"].startswith("0")
                            )
                        ]
                    )
                )
            )
        except:
            seasons = None
        if seasons:
            for x in seasons:
                season_art["%s_%s" % (item, x)] = parse_art(results, language, x)
    return season_art


def parse_art(art, language, season=None):
    if not art:
        return ""
    try:
        if language == "keyart":
            result = [i for i in art if i["lang"] in blank_image_values]
        else:
            if season:
                art = [i for i in art if i["season"] == season]
            result = [i for i in art if i["lang"] == language]
            if not result:
                result = [i for i in art if i["lang"] in blank_image_values]
            if not result and language != "en":
                result = [i for i in art if i["lang"] == "en"]
        result = result[0]["url"]
    except:
        result = ""
    return result


""" all_fanart_images = {
        "poster": [i["url"] for i in poster],
        "fanart": [i["url"] for i in fanart],
        "clearlogo": [i["url"] for i in clearlogo],
        "banner": [i["url"] for i in banner],
        "clearart": [i["url"] for i in clearart],
        "landscape": [i["url"] for i in landscape],
        "discart": discart,
        "keyart": keyart,
} """
