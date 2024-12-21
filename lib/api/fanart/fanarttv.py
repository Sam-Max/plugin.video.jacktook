from functools import cached_property
from functools import wraps
from urllib import parse
from xbmc import getLanguage, ISO_639_1
from lib.api.fanart.apibase import ApiBase, handle_single_item_or_list
from lib.api.fanart.utils import extend_array, md5_hash, valid_id_or_none
from lib.api.jacktook.kodi import kodilog
from lib.utils.kodi_utils import notification


def fanart_guard_response(func):
    @wraps(func)
    def wrapper(*args, **kwarg):
        kodilog("fanart_guard_response")
        import requests

        try:
            response = func(*args, **kwarg)
            
            kodilog(response.status_code)
            kodilog("AAAAAAAAAAAAAAAAAAAAAAAAAa")
            kodilog(response.status_code)
            kodilog("BBBBBBBBBBBBBBBBBBBBBBBBBB")
            
            if response.status_code in [200, 201]:
                return response

            if response.status_code == 404:
                kodilog("FanartTv failed to find {response.url}")
                return None
            else:
                kodilog(f"FanartTv returned a {response.status_code} ({FanartTv.http_codes[response.status_code]}")
            return response
        except requests.exceptions.ConnectionError:
            notification("Error: Connection Error")
            return None
        except Exception as e:
            notification("Error: {e}")
            return None

    return wrapper


def wrap_fanart_object(func):
    @wraps(func)
    def wrapper(*args, **kwarg):
        return {"fanart_object": func(*args, **kwarg)}

    return wrapper


class FanartTv(ApiBase):
    base_url = "https://webservice.fanart.tv/v3/"
    api_key = "fa836e1c874ba95ab08a14ee88e05565"

    http_codes = {200: "Success", 404: "Not Found"}
    normalization = [
        ("name", ("title", "sorttitle"), None),
        ("tmdb_id", "tmdb_id", lambda i: valid_id_or_none(i)),
        ("imdb_id", "imdb_id", lambda i: valid_id_or_none(i)),
        ("art", "art", None),
    ]

    show_normalization = extend_array(
        [
            ("thetvdb_id", "tvdb_id", lambda i: valid_id_or_none(i)),
        ],
        normalization,
    )
    meta_objects = {
        "movie": normalization,
        "season": show_normalization,
        "tvshow": show_normalization,
    }

    def __init__(self, client_key):
        self.language = getLanguage(ISO_639_1)
        self.client_key = client_key
        kodilog(f"Client key: {self.client_key}")
        self.fanart_support = bool(self.client_key)
        kodilog(self.fanart_support)
        self.headers = {"client-key": self.client_key, "api-key": self.api_key}

    @cached_property
    def meta_hash(self):
        return md5_hash(
            [
                self.language,
                self.fanart_support,
                self.base_url,
            ]
        )

    @cached_property
    def session(self):
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3 import Retry

        session = requests.Session()
        retries = Retry(
            total=5, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504]
        )
        session.mount("https://", HTTPAdapter(max_retries=retries, pool_maxsize=100))
        return session

    @staticmethod
    def build_image(url, art, image):
        return {
            "url": url,
            "rating": 5.25 + int(image["likes"]) / 5.0,
            "size": FanartTv._get_image_size(art),
            "language": FanartTv._get_image_language(art, image),
        }

    @staticmethod
    def _get_image_size(art):
        if art in ("hdtvlogo", "hdclearart", "hdmovielogo", "hdmovieclearart"):
            return 800
        elif art in ("clearlogo", "clearart", "movielogo", "movieart", "musiclogo"):
            return 400
        elif art in ("tvbanner", "seasonbanner", "moviebanner"):
            return 1000
        elif art in ("showbackground", "moviebackground"):
            return 1920
        elif art in ("tvposter", "seasonposter", "movieposter"):
            return 1426
        elif art in ("tvthumb", "seasonthumb"):
            return 500
        elif art == "characterart":
            return 512
        elif art == "moviethumb":
            return 1000
        return 0

    @staticmethod
    def _get_image_language(art, image):
        if "lang" not in image:
            return None
        return image["lang"] if image["lang"] not in ("", "00") else None

    @fanart_guard_response
    def _get(self, url, **params):
        kodilog("_get")
        if not self.fanart_support:
            return None
        timeout = params.pop("timeout", 10)
        return self.session.get(
            parse.urljoin(self.base_url, url),
            params=params,
            headers=self.headers,
            timeout=timeout,
        )

    def _get_json(self, url, **params):
        kodilog("_get_json")
        response = self._get(url, **params)
        return response.json() if response else None

    @wrap_fanart_object
    def get_movie(self, tmdb_id):
        return (
            self._handle_response(self._get_json(f"movies/{tmdb_id}"), "movie")
            if self.fanart_support
            else None
        )

    @wrap_fanart_object
    def get_show(self, tvdb_id):
        return (
            self._handle_response(self._get_json(f"tv/{tvdb_id}"), "tvshow")
            if self.fanart_support
            else None
        )

    @wrap_fanart_object
    def get_season(self, tvdb_id, season):
        return (
            self._handle_response(
                self._get_json(f"tv/{tvdb_id}"), "season", season
            )
            if self.fanart_support
            else None
        )

    @handle_single_item_or_list
    def _handle_response(self, response, art_type, season=None):
        kodilog("_handle_response")
        try:
            if response:
                result = {"art": self._handle_art(response, art_type, season)}
                result["info"] = self._normalize_info(
                    self.meta_objects[art_type], response
                )
                return result
        except (ValueError, AttributeError):
            kodilog(
                f"Failed to receive JSON from FanartTv response - response: {response}",
            )
            return None

    def _handle_art(self, item, type, season=None):
        meta = {}
        if type == "movie":
            meta.update(
                self.create_meta_data(item, "clearlogo", ["movielogo", "hdmovielogo"])
            )
            meta.update(self.create_meta_data(item, "discart", ["moviedisc"]))
            meta.update(
                self.create_meta_data(item, "clearart", ["movieart", "hdmovieclearart"])
            )
            meta.update(self.create_meta_data(item, "characterart", ["characterart"]))
            meta.update(
                self.create_meta_data(
                    item,
                    "keyart",
                    ["movieposter"],
                    selector=lambda n, i: self._get_image_language(n, i) is None,
                )
            )
            meta.update(
                self.create_meta_data(
                    item,
                    "poster",
                    ["movieposter"],
                    selector=lambda n, i: self._get_image_language(n, i) is not None,
                )
            )
            meta.update(self.create_meta_data(item, "fanart", ["moviebackground"]))
            meta.update(self.create_meta_data(item, "banner", ["moviebanner"]))
            meta.update(self.create_meta_data(item, "landscape", ["moviethumb"]))
        elif type == "season":
            meta.update(
                self.create_meta_data(
                    item, "clearlogo", ["hdtvlogo", "clearlogo"], season
                )
            )
            meta.update(
                self.create_meta_data(
                    item, "clearart", ["hdclearart", "clearart"], season
                )
            )
            meta.update(
                self.create_meta_data(item, "characterart", ["characterart"], season)
            )
            meta.update(
                self.create_meta_data(item, "landscape", ["seasonthumb"], season)
            )
            meta.update(self.create_meta_data(item, "banner", ["seasonbanner"], season))
            meta.update(
                self.create_meta_data(
                    item,
                    "poster",
                    ["seasonposter"],
                    season,
                    lambda n, i: self._get_image_language(n, i) is not None,
                )
            )
            meta.update(
                self.create_meta_data(
                    item,
                    "keyart",
                    ["seasonposter"],
                    season,
                    lambda n, i: self._get_image_language(n, i) is None,
                )
            )
            meta.update(
                self.create_meta_data(item, "fanart", ["showbackground-season"], season)
            )
        elif type == "tvshow":
            meta.update(
                self.create_meta_data(item, "clearlogo", ["hdtvlogo", "clearlogo"])
            )
            meta.update(
                self.create_meta_data(item, "clearart", ["hdclearart", "clearart"])
            )
            meta.update(self.create_meta_data(item, "characterart", ["characterart"]))
            meta.update(
                self.create_meta_data(
                    item,
                    "keyart",
                    ["tvposter"],
                    selector=lambda n, i: self._get_image_language(n, i) is None,
                )
            )
            meta.update(
                self.create_meta_data(
                    item,
                    "poster",
                    ["tvposter"],
                    selector=lambda n, i: self._get_image_language(n, i) is not None,
                )
            )
            meta.update(self.create_meta_data(item, "fanart", ["showbackground"]))
            meta.update(self.create_meta_data(item, "banner", ["tvbanner"]))
            meta.update(self.create_meta_data(item, "landscape", ["tvthumb"]))
        return meta

    def create_meta_data(self, art, dict_name, art_names, season=None, selector=None):
        art_list = []
        for art_item, name in [(art.get(name), name) for name in art_names]:
            if art_item is None:
                continue
            art_list.extend(
                self.build_image(item["url"], name, item)
                for item in art_item
                if (selector is None or selector(name, item))
                and (
                    season is None
                    or item.get("season", "all") == "all"
                    or int(item.get("season", 0)) == season
                )
            )
        return {dict_name: art_list} if art_list else {}
