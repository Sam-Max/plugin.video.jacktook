import hashlib
import requests
from lib.api.jacktorr.jacktorr import TorrServer
from lib.utils.kodi.kodi_formats import is_picture, is_text, is_video, is_music
from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    JACKTORR_ADDON,
    buffer_and_play,
    build_url,
    kodilog,
    notification,
    refresh,
    show_picture,
    translation,
)
from lib.utils.general.utils import (
    USER_AGENT_HEADER,
    build_list_item,
    get_password,
    get_port,
    get_service_host,
    get_username,
    ssl_enabled,
)
from lib.vendor.bencodepy import bencodepy

from xbmcplugin import addDirectoryItem, endOfDirectory
from xbmcgui import Dialog


if JACKTORR_ADDON:
    torrserver_api = TorrServer(
        get_service_host(), get_port(), get_username(), get_password(), ssl_enabled()
    )


def torrent_status(info_hash):
    status = torrserver_api.get_torrent_info(link=info_hash)
    notification(
        "{}".format(status.get("stat_string")),
        status.get("name"),
        sound=False,
    )


def torrent_files(params):
    info_hash = params.get("info_hash")

    info = torrserver_api.get_torrent_info(link=info_hash)
    file_stats = info.get("file_stats")

    for f in file_stats:
        name = f.get("path")
        id = f.get("id")
        serve_url = torrserver_api.get_stream_url(
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
                file_li.setInfo(info_type, info_labels)
                file_li.setProperty("IsPlayable", "true")

                context_menu_items.append(
                    (
                        translation(30700),
                        buffer_and_play(**kwargs),
                    )
                )

                file_li.addContextMenuItems(context_menu_items)

        if info_type is not None:
            addDirectoryItem(
                ADDON_HANDLE,
                build_url("play_url", url=serve_url, name=name),
                file_li,
            )
        else:
            addDirectoryItem(ADDON_HANDLE, url, file_li)
        endOfDirectory(ADDON_HANDLE)


def torrent_action(params):
    info_hash = params.get("info_hash")
    action_str = params.get("action_str")

    needs_refresh = True

    if action_str == "drop":
        torrserver_api.drop_torrent(info_hash)
    elif action_str == "remove_torrent":
        torrserver_api.remove_torrent(info_hash)
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
        torrserver_api.get_stream_url(
            link=params.get("info_hash"),
            path=params.get("path"),
            file_id=params.get("file_id"),
        )
    )


def display_text(params):
    r = requests.get(
        torrserver_api.get_stream_url(
            link=params.get("info_hash"),
            path=params.get("path"),
            file_id=params.get("file_id"),
        )
    )
    Dialog().textviewer(params.get("path"), r.text)


def extract_magnet_from_url(url: str):
    try:
        response = requests.get(url, timeout=10, headers=USER_AGENT_HEADER)
        if response.status_code == 200:
            content = response.content
            return extract_torrent_metadata(content)
        else:
            kodilog(f"Failed to fetch content from URL: {url}")
            return ""
    except Exception as e:
        kodilog(f"Failed to fetch content from URL: {url}, Error: {e}")
        return ""


def extract_torrent_metadata(content: bytes):
    try:
        torrent_data = bencodepy.decode(content)
        info = torrent_data[b"info"]
        info_encoded = bencodepy.encode(info)
        m = hashlib.sha1()
        m.update(info_encoded)
        info_hash = m.hexdigest()
        return convert_info_hash_to_magnet(info_hash)
    except Exception as e:
        kodilog(f"Error occurred extracting torrent metadata: {e}")
        return ""


def convert_info_hash_to_magnet(info_hash: str) -> str:
    magnet_link = f"magnet:?xt=urn:btih:{info_hash}"
    return magnet_link
