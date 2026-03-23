from threading import Thread
from typing import Any, Dict, List

from xbmcplugin import addDirectoryItem

from lib.api.debrid.alldebrid import AllDebrid
from lib.api.debrid.debrider import Debrider
from lib.api.debrid.premiumize import Premiumize
from lib.api.debrid.realdebrid import RealDebrid
from lib.api.debrid.torbox import Torbox
from lib.clients.debrid.alldebrid import AllDebridHelper
from lib.clients.debrid.debrider import DebriderHelper
from lib.clients.debrid.realdebrid import RealDebridHelper
from lib.clients.debrid.torbox import TorboxHelper
from lib.services.debrid.auth import (
    run_alldebrid_auth,
    run_debrider_auth,
    run_premiumize_auth,
    run_realdebrid_auth,
    run_torbox_auth,
)
from lib.services.debrid.download import run_realdebrid_download
from lib.utils.general.utils import (
    DebridType,
    IndexerType,
    build_list_item,
    check_debrid_enabled,
    get_random_color,
    set_pluging_category,
)
from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    build_url,
    end_of_directory,
    get_setting,
    notification,
    play_info_hash,
    translation,
)


def _start_realdebrid_download(magnet):
    rd_client = RealDebrid(token=str(get_setting("real_debrid_token", "")))
    thread = Thread(target=run_realdebrid_download, args=(rd_client, magnet, False))
    thread.start()


def _start_torbox_download(magnet):
    tb_client = Torbox(token=str(get_setting("torbox_token")))
    thread = Thread(target=tb_client.download, args=(magnet,))
    thread.start()


def _start_premiumize_download(magnet):
    pm_client = Premiumize(token=str(get_setting("premiumize_token")))
    thread = Thread(target=pm_client.download, args=(magnet,), kwargs={"pack": False})
    thread.start()


DEBRID_CLOUD_ACTIONS = {
    DebridType.RD: {"downloads": "get_rd_downloads", "info": "real_debrid_info"},
    DebridType.DB: {"downloads": "get_db_downloads", "info": "debrider_info"},
    DebridType.AD: {"downloads": "get_ad_downloads", "info": "alldebrid_info"},
    DebridType.TB: {"downloads": "get_tb_downloads", "info": "torbox_info"},
}

DEBRID_DOWNLOAD_HANDLERS = {
    "RD": _start_realdebrid_download,
    "TB": _start_torbox_download,
    "PM": _start_premiumize_download,
}

DEBRID_INFO_HANDLERS = {
    DebridType.RD: lambda: RealDebridHelper().get_info(),
    DebridType.AD: lambda: AllDebridHelper().get_info(),
    DebridType.DB: lambda: DebriderHelper().get_info(),
    DebridType.TB: lambda: TorboxHelper().get_info(),
}


def cloud_details(params):
    debrid_name = params.get("debrid_name")
    if debrid_name == DebridType.PM:
        notification("Not yet implemented")
        return

    actions = DEBRID_CLOUD_ACTIONS.get(debrid_name)
    if not actions:
        notification("Unsupported debrid type")
        return

    addDirectoryItem(
        ADDON_HANDLE,
        build_url(actions["downloads"]),
        build_list_item("Downloads", "download.png"),
        isFolder=True,
    )
    addDirectoryItem(
        ADDON_HANDLE,
        build_url(actions["info"]),
        build_list_item("Account Info", "download.png"),
        isFolder=True,
    )
    end_of_directory()


def cloud(params):
    set_pluging_category(translation(90014))
    activated_debrids = [
        debrid for debrid in DebridType.values() if check_debrid_enabled(debrid)
    ]
    for debrid in activated_debrids:
        torrent_li = build_list_item(debrid, "download.png")
        addDirectoryItem(
            ADDON_HANDLE,
            build_url("cloud_details", debrid_name=debrid),
            torrent_li,
            isFolder=True,
        )

    addDirectoryItem(
        ADDON_HANDLE,
        build_url("list_webdav"),
        build_list_item("Webdav", "download.png"),
        isFolder=True,
    )

    end_of_directory()


def real_debrid_info(params):
    DEBRID_INFO_HANDLERS[DebridType.RD]()


def alldebrid_info(params):
    DEBRID_INFO_HANDLERS[DebridType.AD]()


def debrider_info(params):
    DEBRID_INFO_HANDLERS[DebridType.DB]()


def easynews_info(params):
    from lib.clients.easynews import Easynews

    user = str(get_setting("easynews_user") or "")
    password = str(get_setting("easynews_password") or "")
    timeout = int(get_setting("easynews_timeout", "25") or "25")

    if not user or not password:
        notification("Easynews credentials required")
        return

    Easynews(user, password, timeout, notification).get_info()


def get_rd_downloads(params):
    page = int(params.get("page", 1))
    debrid_type = DebridType.RD
    debrid_color = get_random_color(debrid_type, formatted=False)
    formatted_type = f"[B][COLOR {debrid_color}]{debrid_type}[/COLOR][/B]"

    rd_client = RealDebrid(token=str(get_setting("real_debrid_token", "")))
    raw_downloads = rd_client.get_user_downloads_list(page=page)
    downloads: List[Dict[str, Any]] = [
        item for item in raw_downloads if isinstance(item, dict)
    ]

    sorted_downloads = sorted(
        downloads, key=lambda item: str(item.get("filename", "")), reverse=False
    )
    for download in sorted_downloads:
        torrent_li = build_list_item(
            f"{formatted_type} - {download.get('filename')}", "download.png"
        )
        torrent_li.setProperty("IsPlayable", "true")
        addDirectoryItem(
            ADDON_HANDLE,
            build_url(
                "play_info_hash",
                url=download.get("download"),
                title=download.get("filename"),
                debrid_type=debrid_type,
            ),
            torrent_li,
            isFolder=False,
        )

    if downloads:
        addDirectoryItem(
            ADDON_HANDLE,
            build_url("get_rd_downloads", page=page + 1),
            build_list_item("Next Page", "next.png"),
            isFolder=True,
        )

    end_of_directory()


def get_tb_downloads(params):
    debrid_type = DebridType.TB
    debrid_color = get_random_color(debrid_type, formatted=False)
    formatted_type = f"[B][COLOR {debrid_color}]{debrid_type}[/COLOR][/B]"

    raw_downloads = TorboxHelper().get_cloud_downloads()
    downloads: List[Dict[str, Any]] = [
        item for item in raw_downloads if isinstance(item, dict)
    ]

    def _torbox_sort_key(item: Dict[str, Any]):
        return (
            str(item.get("updated_at") or item.get("created_at") or ""),
            str(item.get("name", "")),
        )

    sorted_downloads = sorted(
        downloads,
        key=_torbox_sort_key,
        reverse=True,
    )

    notification(
        f"Torbox Cloud: {len(sorted_downloads)} playable items found", time=2500, sound=False
    ) if params.get("debug") else None

    for download in sorted_downloads:
        torrent_li = build_list_item(
            f"{formatted_type} - {download.get('name')}", "download.png"
        )
        torrent_li.setProperty("IsPlayable", "true")
        addDirectoryItem(
            ADDON_HANDLE,
            build_url(
                "play_media",
                data={
                    "title": download.get("name"),
                    "url": "",
                    "mode": "movie",
                    "type": IndexerType.DEBRID,
                    "debrid_type": debrid_type,
                    "torrent_id": download.get("torrent_id"),
                    "file_id": download.get("file_id"),
                    "info_hash": download.get("info_hash", ""),
                },
            ),
            torrent_li,
            isFolder=False,
        )

    end_of_directory()


def download(magnet, debrid_type):
    handler = DEBRID_DOWNLOAD_HANDLERS.get(debrid_type)
    if not handler:
        notification("Unsupported debrid type")
        return
    handler(magnet)


def rd_auth(params):
    rd_client = RealDebrid(token=str(get_setting("real_debrid_token", "")))
    run_realdebrid_auth(rd_client)


def ad_auth(params):
    ad_client = AllDebrid(token=str(get_setting("alldebrid_token", "")))
    run_alldebrid_auth(ad_client)


def rd_remove_auth(params):
    rd_client = RealDebrid(token=str(get_setting("real_debrid_token", "")))
    rd_client.remove_auth()


def ad_remove_auth(params):
    ad_client = AllDebrid(token=str(get_setting("alldebrid_token", "")))
    ad_client.remove_auth()


def debrider_auth(params):
    debrider_client = Debrider(token=str(get_setting("debrider_token")))
    run_debrider_auth(debrider_client)


def debrider_remove_auth(params):
    debrider_client = Debrider(token=str(get_setting("debrider_token")))
    debrider_client.remove_auth()


def pm_auth(params):
    pm_client = Premiumize(token=str(get_setting("premiumize_token")))
    run_premiumize_auth(pm_client)


def tb_auth(params):
    torbox_client = Torbox(token=str(get_setting("torbox_token")))
    run_torbox_auth(torbox_client)


def tb_remove_auth(params):
    torbox_client = Torbox(token=str(get_setting("torbox_token")))
    torbox_client.remove_auth()


def torbox_info(params):
    DEBRID_INFO_HANDLERS[DebridType.TB]()
