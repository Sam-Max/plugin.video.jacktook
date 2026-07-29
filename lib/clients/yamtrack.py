from urllib.parse import quote, urlsplit, urlunsplit

import requests

from lib.clients.tmdb.utils.utils import tmdb_get
from lib.utils.kodi.utils import get_setting, kodilog

WATCHED_THRESHOLD = 90.0
REQUEST_TIMEOUT = 10


def build_webhook_url(base_url, token):
    """Build a Yamtrack webhook URL without exposing credentials in logs."""
    base_url = str(base_url or "").strip()
    token = str(token or "").strip()
    if not base_url or not token:
        raise ValueError("Yamtrack base URL and token are required")

    try:
        parsed = urlsplit(base_url)
        port = parsed.port
    except ValueError as error:
        raise ValueError("Invalid Yamtrack base URL") from error

    if (
        parsed.scheme.lower() not in ("http", "https")
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Invalid Yamtrack base URL")

    netloc = parsed.hostname
    if ":" in netloc and not netloc.startswith("["):
        netloc = f"[{netloc}]"
    if port is not None:
        netloc = f"{netloc}:{port}"

    path = parsed.path.rstrip("/")
    webhook_path = f"{path}/webhook/jellyfin/{quote(token, safe='')}"
    return urlunsplit((parsed.scheme.lower(), netloc, webhook_path, "", ""))


def _value(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _clean_id(value):
    if value is None or isinstance(value, bool):
        return None
    value = str(value).strip()
    return value or None


def _episode_position(data):
    tv_data = data.get("tv_data")
    if not isinstance(tv_data, dict):
        return None

    try:
        season = int(tv_data.get("season"))
        episode = int(tv_data.get("episode"))
    except (TypeError, ValueError):
        return None
    if season < 0 or episode <= 0:
        return None
    return season, episode


def build_payload(data):
    """Build a Jellyfin-shaped watched payload from Jacktook playback data."""
    ids = data.get("ids")
    if not isinstance(ids, dict):
        return None

    mode = data.get("mode")
    if mode == "movies":
        provider_ids = {}
        tmdb_id = _clean_id(ids.get("tmdb_id"))
        imdb_id = _clean_id(ids.get("imdb_id"))
        if tmdb_id:
            provider_ids["Tmdb"] = tmdb_id
        elif imdb_id:
            provider_ids["Imdb"] = imdb_id
        else:
            return None
        item = {"Type": "Movie", "ProviderIds": provider_ids}
    elif mode == "tv":
        show_tmdb_id = _clean_id(ids.get("tmdb_id"))
        position = _episode_position(data)
        if not show_tmdb_id or position is None:
            return None
        season, episode = position

        external_ids = tmdb_get(
            "episode_external_ids",
            {"id": show_tmdb_id, "season": season, "episode": episode},
        )
        provider_ids = {}
        tvdb_id = _clean_id(_value(external_ids, "tvdb_id"))
        imdb_id = _clean_id(_value(external_ids, "imdb_id"))
        if tvdb_id:
            provider_ids["Tvdb"] = tvdb_id
        elif imdb_id:
            provider_ids["Imdb"] = imdb_id
        else:
            return None

        series_name = str(data.get("query") or "").strip()
        if not series_name:
            show_details = tmdb_get("tv_details", show_tmdb_id)
            series_name = str(_value(show_details, "name") or "").strip()
        if not series_name:
            return None

        item = {
            "Type": "Episode",
            "ProviderIds": provider_ids,
            "SeriesName": series_name,
            "ParentIndexNumber": season,
            "IndexNumber": episode,
        }
    else:
        return None

    item["UserData"] = {"Played": True}
    return {"Event": "Stop", "Item": item}


def send_watched_state(data):
    """Send one completed-playback event when Yamtrack is configured."""
    if not get_setting("yamtrack_enabled", False):
        return False

    try:
        progress = float(data.get("progress") or 0)
    except (TypeError, ValueError):
        return False
    if progress < WATCHED_THRESHOLD:
        return False

    base_url = get_setting("yamtrack_base_url", "")
    token = get_setting("yamtrack_token", "")
    try:
        url = build_webhook_url(base_url, token)
        payload = build_payload(data)
    except Exception as error:
        kodilog(f"[YAMTRACK] Configuration or metadata error ({type(error).__name__})")
        return False
    if payload is None:
        return False

    try:
        response = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
    except Exception as error:
        kodilog(f"[YAMTRACK] Request failed ({type(error).__name__})")
        return False

    if response.status_code != 200:
        kodilog(f"[YAMTRACK] Request rejected with HTTP {response.status_code}")
        return False
    return True
