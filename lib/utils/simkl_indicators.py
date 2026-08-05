from lib.api.simkl import SimklClient, is_simkl_authenticated
from lib.utils.kodi.utils import kodilog, translation

SIMKL_TMDB_ID = "jacktook.simkl.tmdb_id"
SIMKL_MEDIA_TYPE = "jacktook.simkl.media_type"
SIMKL_SEASON = "jacktook.simkl.season"
SIMKL_EPISODE = "jacktook.simkl.episode"
SIMKL_BATCH_SIZE = 100

STATUS_LABELS = {
    "plantowatch": 90983,
    "watching": 90984,
    "completed": 90985,
    "hold": 90986,
    "dropped": 90987,
}


def _property(item, key):
    try:
        return item.getProperty(key)
    except (AttributeError, TypeError):
        return ""


def _descriptor(item):
    tmdb_id = SimklClient._positive_integer(_property(item, SIMKL_TMDB_ID))
    media_type = _property(item, SIMKL_MEDIA_TYPE)
    if not tmdb_id or media_type not in ("movie", "show", "episode"):
        return None
    if media_type != "episode":
        return (media_type, tmdb_id)
    season = SimklClient._non_negative_integer(_property(item, SIMKL_SEASON))
    episode = SimklClient._positive_integer(_property(item, SIMKL_EPISODE))
    if season is None or not episode:
        return None
    return (media_type, tmdb_id, season, episode)


def _response_descriptor(response):
    if not isinstance(response, dict):
        return None
    movie = response.get("movie")
    show = response.get("show")
    if isinstance(movie, dict) and not isinstance(show, dict):
        ids = movie.get("ids")
        tmdb_id = SimklClient._positive_integer(ids.get("tmdb")) if isinstance(ids, dict) else None
        return ("movie", tmdb_id) if tmdb_id else None
    if not isinstance(show, dict) or isinstance(movie, dict):
        return None
    ids = show.get("ids")
    tmdb_id = SimklClient._positive_integer(ids.get("tmdb")) if isinstance(ids, dict) else None
    if not tmdb_id:
        return None
    episode = response.get("episode")
    if episode is None:
        return ("show", tmdb_id)
    if not isinstance(episode, dict):
        return None
    season = SimklClient._non_negative_integer(episode.get("season"))
    number = SimklClient._positive_integer(episode.get("number"))
    if season is None or not number:
        return None
    return ("episode", tmdb_id, season, number)


def _counters(response):
    counters = response.get("counters") if isinstance(response, dict) else None
    if not isinstance(counters, dict):
        return None
    watched = SimklClient._non_negative_integer(counters.get("episodes_watched"))
    aired = SimklClient._positive_integer(counters.get("episodes_aired"))
    total = SimklClient._positive_integer(counters.get("episodes_total"))
    maximum = aired or total
    if watched is None or not maximum or watched > maximum:
        return None
    return watched, maximum


def _valid_indicator(descriptor, response):
    if _response_descriptor(response) != descriptor:
        return None
    result = response.get("result")
    if result not in (True, False, "true", "false", "not_found"):
        return None
    status = response.get("status")
    if status is not None and status not in STATUS_LABELS:
        return None
    if descriptor[0] == "episode":
        return {"watched": result is True or result == "true"}
    indicator = {"status": status}
    if descriptor[0] == "show":
        indicator["counters"] = _counters(response)
    return indicator if status or indicator.get("counters") else None


def get_indicators(descriptors, client=None):
    if not is_simkl_authenticated():
        return {}
    unique_descriptors = list(dict.fromkeys(descriptors))
    if not unique_descriptors:
        return {}
    client = client or SimklClient()
    indicators = {}
    ambiguous = set()
    for start in range(0, len(unique_descriptors), SIMKL_BATCH_SIZE):
        batch = unique_descriptors[start : start + SIMKL_BATCH_SIZE]
        responses = client.get_watched(batch)
        if not isinstance(responses, list):
            continue
        requested = set(batch)
        for response in responses:
            descriptor = _response_descriptor(response)
            if descriptor not in requested or descriptor in ambiguous:
                continue
            indicator = _valid_indicator(descriptor, response)
            if indicator is not None:
                if descriptor in indicators:
                    indicators.pop(descriptor, None)
                    ambiguous.add(descriptor)
                    continue
                indicators[descriptor] = indicator
    return indicators


def _status_label(status):
    return translation(STATUS_LABELS[status]) if status else ""


def _indicator_label(descriptor, indicator):
    if descriptor[0] == "episode":
        return translation(3067) if indicator.get("watched") else ""
    parts = [_status_label(indicator.get("status"))]
    counters = indicator.get("counters")
    if counters:
        parts.append(f"{counters[0]}/{counters[1]}")
    return " | ".join(part for part in parts if part)


def apply_simkl_indicators(items):
    if not is_simkl_authenticated():
        return
    item_descriptors = [(item, _descriptor(item)) for _, item, _ in items]
    indicators = get_indicators([descriptor for _, descriptor in item_descriptors if descriptor])
    for item, descriptor in item_descriptors:
        indicator = indicators.get(descriptor)
        if not indicator:
            continue
        label = _indicator_label(descriptor, indicator)
        if not label:
            continue
        try:
            item.setLabel(f"[COLOR gray][{label}][/COLOR] {item.getLabel()}")
        except (AttributeError, TypeError) as error:
            kodilog(f"[SIMKL] indicator rendering failed ({type(error).__name__})")
