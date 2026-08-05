from lib.api.simkl import SimklClient, is_simkl_authenticated
from lib.utils.kodi.utils import action_url_run, translation


def add_simkl_history_context_menu(media_type, tmdb_id, season=None, episode=None):
    if (
        not is_simkl_authenticated()
        or SimklClient.history_payload(media_type, tmdb_id, season, episode) is None
    ):
        return []
    params = {"media_type": media_type, "tmdb_id": tmdb_id}
    if media_type == "episode":
        params.update({"season": season, "episode": episode})
    return [
        (translation(90991), action_url_run("simkl_update_history", operation="add", **params)),
        (translation(90992), action_url_run("simkl_update_history", operation="remove", **params)),
    ]
