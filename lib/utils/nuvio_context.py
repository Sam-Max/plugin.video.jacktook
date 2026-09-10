from lib.api.nuvio import NuvioClient, is_nuvio_progress_sync_enabled
from lib.utils.kodi.utils import action_url_run, translation


def add_nuvio_history_context_menu(media_type, tmdb_id, season=None, episode=None, title=None):
    if (
        not is_nuvio_progress_sync_enabled()
        or media_type not in ("movie", "episode")
        or NuvioClient._positive_integer(tmdb_id) is None
    ):
        return []
    if media_type == "episode" and (
        NuvioClient._positive_integer(season) is None
        or NuvioClient._positive_integer(episode) is None
    ):
        return []
    params = {"media_type": media_type, "tmdb_id": tmdb_id}
    if media_type == "episode":
        params.update({"season": season, "episode": episode})
    # Carry the display title so the pushed history entry is not blank.
    if isinstance(title, str) and title.strip():
        params["title"] = title.strip()
    return [
        (translation(91044), action_url_run("nuvio_update_history", operation="add", **params)),
        (translation(91045), action_url_run("nuvio_update_history", operation="remove", **params)),
    ]
