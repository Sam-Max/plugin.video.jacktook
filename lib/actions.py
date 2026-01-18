import json
from lib.domain.torrent import TorrentStream
from lib.gui.resolver_window import ResolverWindow
from lib.utils.kodi.utils import ADDON_PATH
from lib.downloader import handle_download_file

def resolve_for_pack_selection(params):
    data = json.loads(params["data"])
    info_hash = data.get("infoHash")
    
    source = TorrentStream(
        guid="",
        url=data.get("url"),
        infoHash=info_hash,
        title=data.get("title", ""),
        size=data.get("size", 0),
        type=data.get("type", "direct"),
        debridType=data.get("debridType"),
        provider=data.get("provider"),
        indexer=data.get("indexer"),
        subindexer=data.get("subindexer"),
        quality=data.get("quality"),
        isPack=data.get("isPack", False),
        languages=data.get("languages", []),
        fullLanguages=data.get("fullLanguages", []),
        publishDate=data.get("publishDate", ""),
        seeders=data.get("seeders", 0),
    )

    item_information = {
        "title": data.get("title"),
        "mode": data.get("mode"),
        "ids": data.get("ids"),
        "tv_data": data.get("tv_data"),
    }

    resolver_window = ResolverWindow(
        "resolver.xml",
        ADDON_PATH,
        source=source,
        item_information=item_information,
    )
    resolver_window.doModal(pack_select=True)
    del resolver_window


def resolve_for_subtitles(params):
    data = json.loads(params["data"])
    info_hash = data.get("infoHash")

    source = TorrentStream(
        url=data.get("url"),
        guid=data.get("guid"),
        infoHash=info_hash,
        title=data.get("title"),
        size=data.get("size"),
        type=data.get("type"),
        debridType=data.get("debridType"),
        provider=data.get("provider"),
        indexer=data.get("indexer"),
        subindexer=data.get("subindexer"),
        quality=data.get("quality"),
        isPack=data.get("isPack"),
        languages=data.get("languages"),
        fullLanguages=data.get("fullLanguages"),
        publishDate=data.get("publishDate"),
        seeders=data.get("seeders"),
    )

    item_information = {
        "title": data.get("title"),
        "mode": data.get("mode"),
        "ids": data.get("ids"),
        "tv_data": data.get("tv_data"),
    }

    resolver_window = ResolverWindow(
        "resolver.xml",
        ADDON_PATH,
        source=source,
        item_information=item_information,
        is_subtitle_download=True,
    )
    resolver_window.doModal()
    del resolver_window



