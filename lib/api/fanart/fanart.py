import requests

API_KEY = "a7ad21743fd710fccb738232f2fbdcfc"
CLIENT_KEY = "fe073550acf157bdb8a4217f215c0882"
BASE_URL = "https://webservice.fanart.tv/v3/{media_type}/{media_id}"
TIMEOUT = 3.0

DEFAULT_FANART = {
    "poster2": "",
    "fanart2": "",
    "banner": "",
    "clearart": "",
    "clearlogo": "",
    "landscape": "",
    "discart": "",
    "fanart_added": False,
}

# Shared HTTP session (persistent, connection pooled)
session = requests.Session()
session.mount(
    "https://webservice.fanart.tv", requests.adapters.HTTPAdapter(pool_maxsize=100)
)


def get_fanart(media_type: str, language: str, media_id: str) -> dict:
    """
    Fetch localized artwork (poster, fanart, clearlogo, etc.) from fanart.tv.
    Supports movies and TV shows, with language fallback: local → English → universal.
    """
    if not media_id:
        return DEFAULT_FANART.copy()

    url = BASE_URL.format(media_type=media_type, media_id=media_id)
    headers = {"client-key": CLIENT_KEY, "api-key": API_KEY}

    try:
        response = session.get(url, headers=headers, timeout=TIMEOUT)
        data = response.json()
    except Exception:
        return DEFAULT_FANART.copy()

    # Handle API errors
    if not data or "error_message" in data:
        return DEFAULT_FANART.copy()

    # Convenience alias
    get = data.get

    if media_type == "movies":
        return {
            "poster": select_art(get("movieposter"), language),
            "fanart": select_art(get("moviebackground"), language),
            "banner": select_art(get("moviebanner"), language),
            "clearart": select_art(
                get("movieart", []) + get("hdmovieclearart", []), language
            ),
            "clearlogo": select_art(
                get("movielogo", []) + get("hdmovielogo", []), language
            ),
            "landscape": select_art(get("moviethumb"), language),
            "discart": select_art(get("moviedisc"), language),
            "fanart_added": True,
        }

    # Default to TV shows
    return {
        "poster": select_art(get("tvposter"), language),
        "fanart": select_art(get("showbackground"), language),
        "banner": select_art(get("tvbanner"), language),
        "clearart": select_art(get("clearart", []) + get("hdclearart", []), language),
        "clearlogo": select_art(get("hdtvlogo", []) + get("clearlogo", []), language),
        "landscape": select_art(get("tvthumb"), language),
        "discart": "",
        "fanart_added": True,
    }


# --- Artwork Selector ---
def select_art(art_list: list, language: str) -> str:
    """
    Return the best matching artwork URL from a list of art objects.
    Preference order: user's language → English → universal.
    Sorts by number of likes (descending).
    """
    if not art_list:
        return ""

    try:
        # 1. User's language (e.g. 'es')
        matches = [
            (x["url"], int(x.get("likes", 0)))
            for x in art_list
            if x.get("lang") == language
        ]

        # 2. English fallback
        if not matches and language != "en":
            matches = [
                (x["url"], int(x.get("likes", 0)))
                for x in art_list
                if x.get("lang") == "en"
            ]

        # 3. Universal fallback ('00' or no lang)
        if not matches:
            matches = [
                (x["url"], int(x.get("likes", 0)))
                for x in art_list
                if x.get("lang") in ("00", "", None)
            ]

        if matches:
            # Sort by likes descending, return top URL
            matches.sort(key=lambda x: x[1], reverse=True)
            return matches[0][0]

    except Exception:
        pass

    return ""


# --- Helper: Merge Results into Existing Metadata ---
def add_fanart(
    media_type: str, language: str, media_id: str, meta: dict
) -> dict:
    """
    Update an existing metadata dictionary with fanart data.
    Always returns a complete dict (never None).
    """
    try:
        meta.update(get_fanart(media_type, language, media_id))
    except Exception:
        meta.update(DEFAULT_FANART)
    return meta
