from lib.utils.tmdb_utils import get_tmdb_media_details
from lib.utils.utils import (
    TMDB_POSTER_URL,
    get_fanart_details,
    clean_auto_play_undesired,
    set_content_type,
    set_watched_title,
    IndexerType,
)
from lib.utils.language_detection import language_codes, langsSet
from lib.clients.debrid.transmission import TransmissionClient
from lib.db.bookmark_db import bookmark_db
from lib.clients.search import search_client
from lib.utils.kodi_utils import (
    cancel_playback,
    get_setting,
    convert_size_to_bytes,
    ADDON_PATH,
)
from lib.player import JacktookPLayer
from lib.play import get_playback_info
from lib.services.filters import FilterBuilder
from lib.services.enrich import (
    EnricherBuilder,
    StatsEnricher,
    QualityEnricher,
    LanguageEnricher,
    IsPackEnricher,
    CacheEnricher,
    FormatEnricher,
    MagnetEnricher,
    FileEnricher,
)
from lib.gui.source_select_new import SourceSelectWindow

from lib.api.jacktook.kodi import kodilog
import json
def search(params):
    """
    Handles media search and playback.
    """
    kodilog("Search params: %s" % params)
    query = params["query"]
    mode = params["mode"]
    media_type = params.get("media_type", "")
    ids = params.get("ids", "")
    tv_data = params.get("tv_data", "")
    direct = params.get("direct", False)
    rescrape = params.get("rescrape", False)

    # Parse TV data if available
    episode, season, ep_name = parse_tv_data(tv_data)

    # Extract TMDb and TVDb IDs
    ids = json.loads(ids.replace("'", '"').replace("None", "null"))
    tmdb_id, tvdb_id, imdb_id = (ids["tmdb_id"], ids["tvdb_id"], ids["imdb_id"])

    # Fetch media details from TMDb
    details = get_tmdb_media_details(tmdb_id, mode)
    poster = f"{TMDB_POSTER_URL}{details.poster_path or ''}"
    overview = details.overview or ""

    # Fetch fanart details
    fanart_data = get_fanart_details(tvdb_id=tvdb_id, tmdb_id=tmdb_id, mode=mode)

    # Prepare item information
    item_info = {
        "episode": episode,
        "season": season,
        "ep_name": ep_name,
        "tvdb_id": tvdb_id,
        "tmdb_id": tmdb_id,
        "imdb_id": imdb_id,
        "tv_data": tv_data,
        "ids": {
            "tmdb_id": tmdb_id,
            "tvdb_id": tvdb_id,
            "imdb_id": imdb_id,
            },
        "mode": mode,
        "poster": poster,
        "fanart": fanart_data["fanart"] or poster,
        "clearlogo": fanart_data["clearlogo"],
        "plot": overview,
        "query": query,
        "media_type": media_type,
    }

    # Set content type and watched title
    set_content_type(mode, media_type)
    set_watched_title(query, ids, mode, media_type)

    # Search for sources
    source = select_source(
        item_info, rescrape, direct
    )
    if not source:
        return

    # Handle selected source
    playback_info = handle_results(source, item_info)
    if not playback_info:
        cancel_playback()
        return

    # Start playback
    player = JacktookPLayer(db=bookmark_db)
    player.run(data=playback_info)
    del player


def parse_tv_data(tv_data):
    """
    Parses TV data into episode, season, and episode name.
    """
    episode, season, ep_name = 0, 0, ""
    if tv_data:
        try:
            ep_name, episode, season = tv_data.split("(^)")
        except ValueError:
            pass
    return int(episode), int(season), ep_name


def select_source(
    info_item, rescrape, direct
):
    """
    Searches for and selects a source.
    """

    def get_sources():
        results = search_client(
            info_item, FakeDialog(), rescrape,
        )
        if not results:
            notification("No results found")
            return None
        return process(results, info_item["mode"], info_item["ep_name"], info_item["episode"], info_item["season"])

    source_select_window = SourceSelectWindow(
        "source_select_new.xml",
        ADDON_PATH,
        item_information=info_item,
        get_sources=get_sources,
    )
    source = source_select_window.doModal()
    del source_select_window
    return source


def process(results, mode, ep_name, episode, season):
    """
    Processes and filters search results.
    """
    sort_by = get_setting("indexers_sort_by")
    limit = int(get_setting("indexers_total_results"))

    enricher = (
        EnricherBuilder()
        .add(FileEnricher())
        .add(StatsEnricher(size_converter=convert_size_to_bytes))
        .add(IsPackEnricher(season) if season else None)
        .add(MagnetEnricher())
        .add(QualityEnricher())
        .add(LanguageEnricher(language_codes, langsSet))
        .add(
            CacheEnricher(
                [
                    (
                        TransmissionClient(
                            get_setting("transmission_host"),
                            get_setting("transmission_folder"),
                            get_setting("transmission_user"),
                            get_setting("transmission_pass"),
                        )
                        if get_setting("transmission_enabled")
                        else None
                    ),
                ]
            )
        )
        .add(FormatEnricher())
    )
    results = enricher.build(results)

    filters = FilterBuilder().dedupe_by_infoHash().limit(limit)
    if get_setting("stremio_enabled") and get_setting("torrent_enable"):
        filters.filter_by_source()
    if mode == "tv" and get_setting("filter_by_episode"):
        filters.filter_by_episode(ep_name, episode, season)
    if sort_by == "Seeds":
        filters.sort_by("seeders", ascending=False)
    elif sort_by == "Size":
        filters.sort_by("size", ascending=False)
    elif sort_by == "Date":
        filters.sort_by("publishDate", ascending=False)
    elif sort_by == "Quality":
        filters.sort_by("quality_sort", ascending=False)
        filters.sort_by("seeders", ascending=False)
    elif sort_by == "Cached":
        filters.sort_by("isCached", ascending=False)
    return filters.build(results)


def handle_results(source, info_item):
    """
    Handles the selected source and prepares playback information.
    """
    if not source:
        return None

    cache_sources = source.get("cache_sources", [])
    for cache_source in cache_sources:
        if cache_source.get("instant_availability"):
            playable_url = cache_source.get("playable_url")
            return {
                **info_item,
                "title": source["title"],
                "type": source["type"],
                "indexer": source["indexer"],
                "url": playable_url,
                "info_hash": source.get("info_hash", ""),
                "is_torrent": False,
                "is_pack": False,
            }

    return get_playback_info(
        {
            **info_item,
            "title": source["title"],
            "type": IndexerType.TORRENT,
            "indexer": source["indexer"],
            "info_hash": source.get("info_hash", ""),
            "magnet": source.get("magnet", ""),
            "is_pack": False,
            "is_torrent": True,
            "url": source["magnet"],
        }
    )


class FakeDialog:
    """
    A placeholder dialog class for mocking progress updates.
    """

    def create(self, message: str):
        pass

    def update(self, percent: int, title: str, message: str):
        pass
