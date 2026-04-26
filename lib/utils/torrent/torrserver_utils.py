import hashlib
import json
from io import BytesIO
import os
import requests
from datetime import timedelta
from urllib.parse import quote
from lib.clients.subtitle.deepl import DeepLTranslator
from lib.clients.subtitle.submanager import SubtitleManager
from lib.db.cached import cache
from lib.utils.kodi.kodi_formats import is_picture, is_text, is_video, is_music
from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    ADDON_PROFILE_PATH,
    JACKTORR_ADDON,
    action_url_run,
    buffer_and_play,
    build_url,
    end_of_directory,
    get_setting,
    kodilog,
    notification,
    refresh,
    show_picture,
    translation,
)
from lib.utils.general.utils import (
    USER_AGENT_HEADER,
    build_list_item,
    get_info_hash_from_magnet,
    set_pluging_category,
)
from lib.vendor.bencodepy import bencodepy

from xbmcplugin import addDirectoryItem
from xbmcgui import Dialog

import xbmc
import xbmcgui

from lib.utils.torrent.torrserver_init import get_torrserver_api


def _buffer_and_play_url(info_hash, file_id, path):
    return (
        "plugin://plugin.video.jacktorr/buffer_and_play"
        f"?info_hash={info_hash}&file_id={file_id}&path={quote(path or '')}"
    )


def _select_torrent_video_file(info_hash):
    info = get_torrserver_api().get_torrent_info(link=info_hash)
    files = info.get("file_stats") or []
    video_files = [f for f in files if is_video(f.get("path", ""))]
    if not video_files:
        notification("No video files found")
        return None
    if len(video_files) == 1:
        return video_files[0]

    selected = Dialog().select("Select file", [f.get("path", "") for f in video_files])
    if selected < 0:
        return None
    return video_files[selected]


def torrent_status(info_hash):
    status = get_torrserver_api().get_torrent_info(link=info_hash)
    notification(
        "{}".format(status.get("stat_string")),
        status.get("name"),
        sound=False,
    )


def torrent_files(params):
    info_hash = params.get("info_hash")

    info = get_torrserver_api().get_torrent_info(link=info_hash)
    file_stats = info.get("file_stats")

    set_pluging_category(info.get("title", ""))

    for f in file_stats:
        name = f.get("path")
        id = f.get("id")
        serve_url = get_torrserver_api().get_stream_url(
            link=info_hash, path=f.get("path"), file_id=id
        )
        file_li = build_list_item(name, "download.png")
        file_li.setPath(serve_url)

        context_menu_items = []
        info_type = None
        info_labels = {"title": info.get("title")}
        kwargs = dict(info_hash=info_hash, file_id=id, path=name)

        if is_picture(name):
            url = build_url("display_picture", **kwargs)
            file_li.setInfo("pictures", info_labels)
        elif is_text(name):
            url = build_url("display_text", **kwargs)
        else:
            url = serve_url
            if is_video(name):
                info_type = "video"
            elif is_music(name):
                info_type = "music"

            if info_type is not None:
                jacktorr_url = _buffer_and_play_url(info_hash, id, name)
                if info_type == "video":
                    file_li.getVideoInfoTag().setTitle(info_labels.get("title", ""))
                elif info_type == "music":
                    file_li.getMusicInfoTag().setTitle(info_labels.get("title", ""))
                file_li.setProperty("IsPlayable", "true")
                file_li.setPath(jacktorr_url)

                context_menu_items.append(
                    (
                        translation(30700),
                        buffer_and_play(**kwargs),
                    )
                )

                if info_type == "video":
                    parsed_data = _parse_torrent_meta(info)
                    parsed_ids = parsed_data.get("ids", {}) if isinstance(parsed_data.get("ids", {}), dict) else {}
                    meta = {
                        "title": parsed_data.get("title") or info.get("title", ""),
                        "mode": parsed_data.get("mode", ""),
                        "ids": {
                            "tmdb_id": parsed_ids.get("tmdb_id", ""),
                            "tvdb_id": parsed_ids.get("tvdb_id", ""),
                            "imdb_id": parsed_ids.get("imdb_id"),
                            "original_id": parsed_ids.get("original_id", ""),
                        },
                        "tv_data": parsed_data.get("tv_data", {}),
                    }
                    context_menu_items.append(
                        (
                            translation(90082),
                            action_url_run(
                                "download_and_play_subtitles",
                                hash=info_hash,
                                file_id=id,
                                path=name,
                                meta=json.dumps(meta),
                            ),
                        )
                    )

                context_menu_items.append(
                    (
                        translation(30705),
                        action_url_run(
                            "torrent_action",
                            info_hash=info_hash,
                            action_str="remove_torrent",
                        ),
                    )
                )
                context_menu_items.append(
                    (
                        translation(30707),
                        action_url_run(
                            "torrent_action",
                            info_hash=info_hash,
                            action_str="torrent_status",
                        ),
                    )
                )

                file_li.addContextMenuItems(context_menu_items)

        if info_type is not None:
            addDirectoryItem(
                ADDON_HANDLE,
                jacktorr_url,
                file_li,
            )
        else:
            addDirectoryItem(ADDON_HANDLE, url, file_li)
    end_of_directory()


def torrent_action(params):
    info_hash = params.get("info_hash")
    action_str = params.get("action_str")

    needs_refresh = True

    if action_str == "drop":
        get_torrserver_api().drop_torrent(info_hash)
    elif action_str == "remove_torrent":
        get_torrserver_api().remove_torrent(info_hash)
    elif action_str == "torrent_status":
        torrent_status(info_hash)
        needs_refresh = False
    else:
        kodilog(f"Unknown action: {action_str}")
        needs_refresh = False

    if needs_refresh:
        refresh()


def display_picture(params):
    show_picture(
        get_torrserver_api().get_stream_url(
            link=params.get("info_hash"),
            path=params.get("path"),
            file_id=params.get("file_id"),
        )
    )


def display_text(params):
    r = requests.get(
        get_torrserver_api().get_stream_url(
            link=params.get("info_hash"),
            path=params.get("path"),
            file_id=params.get("file_id"),
        )
    )
    Dialog().textviewer(params.get("path"), r.text)


def add_source_to_torrserver(
    magnet="", url="", info_hash="", title="", poster="", data=""
):
    if not JACKTORR_ADDON:
        notification(translation(30253))
        return None

    api = get_torrserver_api()
    if api is None:
        notification(translation(30253))
        return None

    try:
        added_hash = None
        kodilog(
            "add_source_to_torrserver input: info_hash={!r}, title={!r}, has_magnet={}, has_url={}, has_data={}".format(
                info_hash,
                title,
                bool(magnet),
                bool(url),
                bool(data),
            )
        )

        if url and url.startswith("http"):
            try:
                response = requests.get(url, timeout=15, headers=USER_AGENT_HEADER)
                response.raise_for_status()
                torrent_obj = BytesIO(response.content)
                torrent_obj.name = "torrent.torrent"
                added_hash = api.add_torrent_obj(
                    torrent_obj, title=title, poster=poster
                )
                kodilog(
                    "add_source_to_torrserver added torrent URL: returned_hash={!r}".format(
                        added_hash
                    )
                )
            except Exception as exc:
                kodilog(f"Failed to add torrent URL to TorrServer: {exc}")

        if not added_hash:
            if not magnet and info_hash:
                magnet = convert_info_hash_to_magnet(info_hash)

            if magnet:
                added_hash = api.add_magnet(magnet, title=title, poster=poster)
                kodilog(
                    "add_source_to_torrserver added magnet: returned_hash={!r}".format(
                        added_hash
                    )
                )
            else:
                notification(translation(90361))
                return None

        if added_hash and data:
            try:
                meta = json.loads(data) if isinstance(data, str) else {}
                magnet_hash = ""
                if magnet:
                    try:
                        magnet_hash = get_info_hash_from_magnet(magnet)
                    except Exception as exc:
                        kodilog(f"Failed to extract metadata hash from magnet: {exc}")

                hash_candidates = _metadata_hash_candidates(added_hash, info_hash, magnet_hash)
                for hash_candidate in hash_candidates:
                    save_torrent_meta(hash_candidate, meta)
            except Exception as exc:
                kodilog(f"Failed to parse/save torrent metadata for {added_hash}: {exc}")
        elif added_hash:
            kodilog(f"add_source_to_torrserver no metadata data provided for {added_hash}")

        notification(translation(90360))
        return added_hash
    except Exception as exc:
        kodilog(f"Failed to add source to TorrServer: {exc}")
        notification(str(exc))
        return None


def extract_magnet_from_url(url: str):
    try:
        response = requests.get(url, timeout=10, headers=USER_AGENT_HEADER)
        if response.status_code == 200:
            return extract_torrent_metadata(response.content)
        else:
            kodilog(f"Failed to fetch content from URL: {url}")
            return None
    except Exception as e:
        kodilog(f"Failed to fetch content from URL: {url}, Error: {e}")
        return None


def extract_torrent_metadata(content: bytes):
    kodilog("Extracting torrent metadata...")
    try:
        torrent_data = bencodepy.decode(content)
        info = torrent_data[b"info"]
        info_encoded = bencodepy.encode(info)
        info_hash = hashlib.sha1(info_encoded).hexdigest()
        return convert_info_hash_to_magnet(info_hash)
    except Exception as e:
        kodilog(f"Error occurred extracting torrent metadata: {e}")
        return None


def convert_info_hash_to_magnet(info_hash: str) -> str:
    return f"magnet:?xt=urn:btih:{info_hash}"


_TORRENT_META_CACHE_PREFIX = "torrent_meta:"


def _normalize_torrent_hash(info_hash):
    return str(info_hash or "").strip().lower()


def _metadata_hash_candidates(*hashes):
    candidates = []
    for info_hash in hashes:
        normalized = _normalize_torrent_hash(info_hash)
        if normalized and normalized not in candidates:
            candidates.append(normalized)
    return candidates


def save_torrent_meta(info_hash, meta):
    """Persist torrent metadata locally, keyed by info hash.

    This avoids reliance on TorrServer's undocumented ``data`` field.
    """
    info_hash = _normalize_torrent_hash(info_hash)
    if not info_hash:
        return

    key = f"{_TORRENT_META_CACHE_PREFIX}{info_hash}"
    try:
        cache.set(key, meta, expires=timedelta(days=365))
    except Exception as exc:
        kodilog(f"Failed to save torrent meta for {info_hash}: {exc}")


def get_torrent_meta(info_hash):
    """Retrieve torrent metadata from local cache.

    Returns the stored dict or an empty dict if not found.
    """
    info_hash = _normalize_torrent_hash(info_hash)
    if not info_hash:
        return {}

    key = f"{_TORRENT_META_CACHE_PREFIX}{info_hash}"
    try:
        result = cache.get(key)
        if result and isinstance(result, dict):
            return result
    except Exception as exc:
        kodilog(f"Failed to load torrent meta for {info_hash}: {exc}")
    return {}


def _parse_torrent_meta(info):
    """Retrieve torrent metadata from local cache, keyed by hash."""
    info_hash = info.get("hash")
    if info_hash:
        local_meta = get_torrent_meta(info_hash)
        if local_meta:
            return local_meta
    return {}


def _normalize_media_ids(ids):
    normalized = ids.copy() if isinstance(ids, dict) else {}
    normalized.setdefault("tmdb_id", "")
    normalized.setdefault("tvdb_id", "")
    normalized.setdefault("imdb_id", "")
    normalized.setdefault("original_id", "")
    return normalized


def download_torrent_subtitles(params):
    info_hash = params.get("hash")
    meta_str = params.get("meta", "{}")
    try:
        meta = json.loads(meta_str)
    except Exception:
        meta = {}

    ids = _normalize_media_ids(meta.get("ids", {}))
    imdb_id = ids.get("imdb_id")
    title = meta.get("title")
    mode = meta.get("mode") or ("tv" if meta.get("tv_data", {}).get("season") else "movies")
    tv_data = meta.get("tv_data", {})

    if not imdb_id and not title:
        notification("Insufficient metadata")
        return

    data = {"title": title, "mode": mode, "ids": ids, "tv_data": tv_data}

    folder_path = os.path.join(ADDON_PROFILE_PATH, "subtitles", info_hash)
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    manager = SubtitleManager(data=data, notification=notification)
    result = manager.fetch_subtitles(auto_select=False, folder_path=folder_path)

    if result:
        notification("Subtitles downloaded successfully")
        selected_file = _select_torrent_video_file(info_hash)
        if selected_file:
            playback_url = _buffer_and_play_url(
                info_hash, selected_file.get("id"), selected_file.get("path")
            )
            listitem = xbmcgui.ListItem(label=title, path=playback_url)
            listitem.setSubtitles(result)
            xbmc.Player().play(playback_url, listitem)
    else:
        if manager.last_fetch_status == "not_found":
            notification(translation(90252))
        elif manager.last_fetch_status == "not_selected":
            notification(translation(90253))
        elif manager.last_fetch_status == "no_imdb":
            notification(translation(90299))
        else:
            notification(translation(90252))


def download_and_play_subtitles(params):
    info_hash = params.get("hash")
    file_id = params.get("file_id")
    path = params.get("path")
    meta_str = params.get("meta", "{}")
    try:
        meta = json.loads(meta_str)
    except Exception:
        meta = {}

    ids = _normalize_media_ids(meta.get("ids", {}))
    imdb_id = ids.get("imdb_id")
    title = meta.get("title")
    mode = meta.get("mode") or ("tv" if meta.get("tv_data", {}).get("season") else "movies")
    tv_data = meta.get("tv_data", {})

    if not imdb_id and not title:
        notification("Insufficient metadata")
        return

    data = {"title": title, "mode": mode, "ids": ids, "tv_data": tv_data}

    manager = SubtitleManager(data=data, notification=notification)
    subtitle_paths = manager.fetch_subtitles(auto_select=False)

    if not subtitle_paths:
        if manager.last_fetch_status == "no_imdb":
            notification(translation(90299))
        else:
            notification(translation(90252))
        return

    playback_url = _buffer_and_play_url(info_hash, file_id, path)
    listitem = xbmcgui.ListItem(label=title, path=playback_url)
    listitem.setSubtitles(subtitle_paths)
    xbmc.Player().play(playback_url, listitem)
