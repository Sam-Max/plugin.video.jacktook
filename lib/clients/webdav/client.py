import requests
from lib.api.webdav.webdav import WebDAVClient
from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    build_url,
    dialog_ok,
    end_of_directory,
    get_setting,
    kodilog,
    notification,
    show_picture,
)
from xbmcgui import ListItem
from xbmcplugin import (
    addDirectoryItem,
)
from xbmcplugin import addSortMethod, SORT_METHOD_LABEL_IGNORE_THE, SORT_METHOD_FILE
from xbmcgui import Dialog


def list_webdav(params):
    relative_path = params.get("path", "").strip("/")

    client = WebDAVClient(
        get_setting("webdav_hostname"),
        get_setting("webdav_username"),
        get_setting("webdav_password"),
        get_setting("webdav_port"),
        get_setting("webdav_remote_path"),
    )

    items = client.list_dir(relative_path)

    for item in items:
        list_item = ListItem(label=item["name"])
        url = ""
        is_folder = False

        # --- FOLDERS ---
        if item["type"] == "folder":
            new_relative_path = (
                f"{relative_path}/{item['name']}" if relative_path else item["name"]
            )
            url = build_url("list_webdav", path=new_relative_path)
            is_folder = True

        # --- VIDEOS ---
        elif item["type"] == "video":
            list_item.setProperty("IsPlayable", "true")
            info_tag = list_item.getVideoInfoTag()
            info_tag.setTitle(item["name"])
            url = build_url("play_url", url=item["url"], name=item["name"])
            is_folder = False

        # --- AUDIO ---
        elif item["type"] == "audio":
            list_item.setInfo("music", {"title": item["name"]})
            list_item.setProperty("IsPlayable", "true")
            url = build_url("play_url", url=item["url"], name=item["name"])
            is_folder = False

        # --- IMAGES ---
        elif item["type"] == "image":
            list_item.setProperty("IsPlayable", "false")
            list_item.setArt({"thumb": item["url"]})
            list_item.setInfo("pictures", {"title": item["name"]})

            name_parts = item["name"].rsplit(".", 1)
            ext = name_parts[-1].lower() if len(name_parts) > 1 else "jpeg"
            mime = f"image/{ext}" if ext not in ["jpg", "jpeg"] else "image/jpeg"
            list_item.setMimeType(mime)

            url = build_url("show_picture_webdav", url=item["url"])
            is_folder = False
        elif item["type"] == "text":
            list_item.setProperty("IsPlayable", "false")
            url = build_url("display_text_webdav", url=item["url"], title=item["name"])
            is_folder = False
        else:
            list_item.setProperty("IsPlayable", "false")
            url = item["url"]
            is_folder = False

        addDirectoryItem(
            handle=ADDON_HANDLE, url=url, listitem=list_item, isFolder=is_folder
        )

    addSortMethod(ADDON_HANDLE, SORT_METHOD_LABEL_IGNORE_THE)
    addSortMethod(ADDON_HANDLE, SORT_METHOD_FILE)

    end_of_directory()


def webdav_provider_test(params):
    client = WebDAVClient(
        get_setting("webdav_hostname"),
        get_setting("webdav_username"),
        get_setting("webdav_password"),
        get_setting("webdav_port"),
        get_setting("webdav_remote_path"),
    )
    result = client.test_connection()
    if result["success"]:
        dialog_ok("WebDAV", result["message"])
    else:
        dialog_ok("WebDAV Error", result["message"])


def display_text_webdav(params):
    url = params.get("url")
    title = params.get("title", "WebDAV Text Viewer")
    if not url:
        return
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        r.encoding = r.apparent_encoding
        content = r.text
        Dialog().textviewer(title, content)
    except requests.exceptions.RequestException as e:
        kodilog(f"Error downloading text file ({url}): {e}")
        notification("Download Error", f"Failed to download text: {title}")
    except Exception as e:
        kodilog(f"General error displaying text: {e}")
        notification("General Error", "Could not display text file.")


def show_picture_webdav(params):
    show_picture(url=params.get("url"))
