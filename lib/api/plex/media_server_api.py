from http import HTTPStatus
from http.client import HTTPException
import json
import requests
from requests.exceptions import ConnectionError, Timeout
from lib.api.jacktook.kodi import kodilog
from lib.api.plex.settings import settings
from lib.api.plex.models.plex_models import (
    PlexEpisodeMeta,
    PlexLibrarySection,
    PlexMediaMeta,
    PlexMediaType,
    PlexServer,
)
from lib.api.plex.utils import PlexUnauthorizedError


def check_server_connection(url, access_token):
    try:
        response = requests.get(
            url,
            params={
                "X-Plex-Token": access_token,
            },
            timeout=settings.plex_requests_timeout,
        )
        if response.status_code != HTTPStatus.OK:
            return False
        return True
    except (Timeout, ConnectionError):
        return False


def get_servers(url, token):
    json = get_json(
        url=f"{url}/resources",
        params={
            "includeHttps": 1,
            "includeRelay": 1,
            "X-Plex-Token": token,
            "X-Plex-Client-Identifier": settings.identifier,
        },
    )
    return [
        PlexServer(**server)
        for server in json
        if "server" in server["provides"] and "accessToken" in server
    ]


def get_sections(url, token):
    json = get_json(
        url=f"{url}/library/sections",
        params={
            "X-Plex-Token": token,
        },
    )
    return [
        PlexLibrarySection(**section)
        for section in json["MediaContainer"]["Directory"]
        if section["type"] in {PlexMediaType.movie, PlexMediaType.show}
    ]


def get_section_media(
    url,
    token: str,
    section_id: str,
    skip: int,
    search: str,
):
    params = {
        "includeGuids": 1,
        "X-Plex-Container-Start": skip,
        "X-Plex-Container-Size": 100,
        "X-Plex-Token": token,
    }
    if search:
        params["title"] = search
    json = get_json(
        url=f"{url}/library/sections/{section_id}/all",
        params=params,
    )
    metadata = json["MediaContainer"].get("Metadata", [])
    return [PlexMediaMeta(**meta) for meta in metadata]


def get_media(url, token, guid, get_only_first=False):
    json = get_json(
        url=f"{url}/library/all",
        params={
            "guid": guid,
            "X-Plex-Token": token,
        },
    )
    kodilog(f"get_media/library/all: {json}")
    media_sections = json["MediaContainer"].get("Metadata", [])
    media_metas = []
    for section in media_sections:
        json = get_json(
            url=f"{url}/library/metadata/{section['ratingKey']}",
            params={
                "X-Plex-Token": token,
                "includeElements": "Stream",
            },
        )
        metadata = json["MediaContainer"]["Metadata"][0]
        kodilog(f"get_media/library/metadata/: {json}")
        media_metas.append(PlexMediaMeta(**metadata))
        if get_only_first:
            break
    return media_metas


def get_all_episodes(url, token, key):
    json = get_json(
        url=str(f"{url}/{key[1:]}").replace("/children", "/allLeaves"),
        params={
            "X-Plex-Token": token,
        },
    )
    metadata = json["MediaContainer"].get("Metadata", [])
    return [PlexEpisodeMeta(**meta) for meta in metadata]


def imdb_to_plex_id(imdb_id, token, mode, media_type):
    json = get_json(
        url="https://metadata.provider.plex.tv/library/metadata/matches",
        params={
            "X-Plex-Token": token,
            "type": 1 if (media_type == "movies" or mode =="movies") else 2,
            "title": f"imdb-{imdb_id}",
            "guid": f"com.plexapp.agents.imdb://{imdb_id}?lang=en",
        },
    )
    media_container = json["MediaContainer"]
    if media_container["totalSize"]:
        return media_container["Metadata"][0]["guid"]


def get_episode_guid(url, token, show_guid, season, episode):
    all_episodes = get_all_episodes(
        url=url,
        token=token,
        key=show_guid,
    )
    for metadata in all_episodes:
        if str(metadata.parent_index) == season and str(metadata.index) == episode:
            return metadata.guid


def convert_to_plex_id(url, access_token, auth_token, id, mode, media_type, season, episode):
    plex_id = imdb_to_plex_id(id, auth_token, mode, media_type)
    if not plex_id:
        return None

    if mode == "tv" or media_type == "tv":
        media = get_media(
            url=url,
            token=access_token,
            guid=plex_id,
        )
        for meta in media:
            plex_id = get_episode_guid(
                url=url,
                token=access_token,
                show_guid=meta.key,
                season=season,
                episode=episode,
            )
            if plex_id:
                break
        else:
            return None

    return plex_id


def get_json(url, params=None):
    if params is None:
        params = {}
    try:
        response = requests.get(
            url,
            params=params,
            headers={"accept": "application/json"},
            timeout=settings.plex_requests_timeout,
        )
        if response.status_code in (401, 403):
            raise PlexUnauthorizedError()
        if response.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail="Received error from plex server",
            )
        return json.loads(response.content)
    except TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="Plex server timeout error",
        )
