from lib.api.simkl import SimklClient, is_simkl_authenticated
from lib.utils.kodi.utils import dialogyesno, notification, refresh, translation


def update_simkl_history(params):
    if not is_simkl_authenticated() or not isinstance(params, dict):
        return
    operation = params.get("operation")
    media_type = params.get("media_type")
    if operation not in ("add", "remove") or media_type not in ("movie", "episode"):
        return
    tmdb_id = params.get("tmdb_id")
    season = params.get("season")
    episode = params.get("episode")
    if SimklClient.history_payload(media_type, tmdb_id, season, episode) is None:
        return
    if (
        operation == "remove"
        and media_type == "movie"
        and not dialogyesno(translation(90993), translation(90994))
    ):
        return
    if not SimklClient().update_history(operation, media_type, tmdb_id, season, episode):
        notification(translation(90996), time=3000)
        return
    notification(translation(90995), time=3000)
    refresh()
