from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

from lib.clients.stremio.helpers import (
    get_addon_by_base_url,
    get_selected_stream_addons,
)
from lib.clients.stremio.addon_client import StremioAddonClient
from lib.db.cached import cache
from lib.domain.torrent import TorrentStream
from lib.gui.custom_dialogs import source_select
from lib.player import JacktookPLayer
from lib.utils.clients.utils import get_client, update_dialog
from lib.utils.general.utils import (
    DialogListener,
    Indexer,
    SearchVariant,
    cache_results,
    get_cached_results,
    pre_process,
    post_process,
    build_media_metadata,
    set_content_type,
    set_watched_title,
    clean_auto_play_undesired,
    normalize_tv_data,
    safe_json_loads,
)
from lib.utils.debrid.debrid_utils import check_debrid_cached
from lib.utils.kodi.settings import auto_play_enabled, get_setting
from lib.utils.player.utils import resolve_playback_url
from lib.utils.kodi.utils import (
    notification,
    cancel_playback,
    kodilog,
    translation,
    close_busy_dialog,
    ADDON_PATH,
)

from lib.gui.search_status_window import SearchTaskManager, SearchStatusWindow

import xbmc
from xbmcgui import Dialog


TITLE_LANGUAGE_LOCALIZED_FIRST = "localized_first"
TITLE_LANGUAGE_ENGLISH_FIRST = "english_first"
TITLE_LANGUAGE_ENGLISH_ONLY = "english_only"


def _clean_title_candidate(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _unique_title_candidates(candidates: List[str]) -> List[str]:
    unique = []
    seen = set()

    for candidate in candidates:
        cleaned = _clean_title_candidate(candidate)
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(cleaned)

    return unique


def _normalize_search_variant(variant) -> str:
    allowed = {
        SearchVariant.DEFAULT,
        SearchVariant.TITLE_YEAR,
        SearchVariant.ORIGINAL_TITLE,
        SearchVariant.ORIGINAL_TITLE_YEAR,
    }
    return variant if variant in allowed else SearchVariant.DEFAULT


def _normalize_title_language_mode(mode) -> str:
    allowed = {
        TITLE_LANGUAGE_LOCALIZED_FIRST,
        TITLE_LANGUAGE_ENGLISH_FIRST,
        TITLE_LANGUAGE_ENGLISH_ONLY,
    }
    return mode if mode in allowed else TITLE_LANGUAGE_LOCALIZED_FIRST


def _extract_english_tmdb_title(details, mode: str) -> str:
    translations = getattr(details, "translations", None)
    entries = getattr(translations, "translations", translations)
    if not entries:
        return ""

    title_key = "title" if mode == "movies" else "name"

    for entry in entries:
        if getattr(entry, "iso_639_1", "") != "en":
            continue

        data = getattr(entry, "data", None)
        if not data:
            continue

        return _clean_title_candidate(getattr(data, title_key, ""))

    return ""


def _build_title_fallback_queries(
    query: str,
    ids: dict,
    mode: str,
    variant: str = SearchVariant.DEFAULT,
    year: Optional[int] = None,
    title_language_mode: Optional[str] = None,
) -> List[str]:
    variant = _normalize_search_variant(variant)
    title_language_mode = _normalize_title_language_mode(
        title_language_mode
        if title_language_mode is not None
        else get_setting("search_title_language_mode", TITLE_LANGUAGE_LOCALIZED_FIRST)
    )
    candidates = []

    cleaned_query = _clean_title_candidate(query)
    cleaned_year = _clean_title_candidate(year)

    localized_candidate = ""
    if cleaned_query and variant == SearchVariant.DEFAULT:
        localized_candidate = cleaned_query
    elif cleaned_query and cleaned_year and variant == SearchVariant.TITLE_YEAR:
        localized_candidate = f"{cleaned_query} {cleaned_year}"

    if localized_candidate:
        candidates.append(localized_candidate)

    if not ids:
        return _unique_title_candidates(candidates)

    tmdb_id = ids.get("tmdb_id")
    if not tmdb_id or mode not in ("movies", "tv"):
        return _unique_title_candidates(candidates)

    try:
        from lib.clients.tmdb.utils.utils import get_tmdb_media_details

        details = get_tmdb_media_details(tmdb_id, mode)
    except Exception as e:
        kodilog(f"Failed to load TMDB titles for fallback: {e}")
        details = None

    if not details:
        return _unique_title_candidates(candidates)

    english_title = _extract_english_tmdb_title(details, mode)
    original_title = getattr(details, "original_title", "") or getattr(
        details, "original_name", ""
    )

    english_candidate = ""
    original_candidate = ""
    if variant == SearchVariant.DEFAULT:
        english_candidate = english_title
        original_candidate = original_title
    elif variant == SearchVariant.TITLE_YEAR and cleaned_year:
        if english_title:
            english_candidate = f"{english_title} {cleaned_year}"
        if original_title:
            original_candidate = f"{original_title} {cleaned_year}"

    if variant == SearchVariant.DEFAULT:
        if title_language_mode == TITLE_LANGUAGE_ENGLISH_ONLY:
            candidates = [english_candidate, original_candidate]
            if not any(candidates) and localized_candidate:
                candidates.append(localized_candidate)
        elif title_language_mode == TITLE_LANGUAGE_ENGLISH_FIRST:
            candidates = [english_candidate, localized_candidate, original_candidate]
        else:
            candidates = [localized_candidate, english_candidate, original_candidate]
    elif variant == SearchVariant.TITLE_YEAR:
        if title_language_mode == TITLE_LANGUAGE_ENGLISH_ONLY:
            candidates = [english_candidate, original_candidate]
            if not any(candidates) and localized_candidate:
                candidates.append(localized_candidate)
        elif title_language_mode == TITLE_LANGUAGE_ENGLISH_FIRST:
            candidates = [english_candidate, localized_candidate, original_candidate]
        else:
            candidates = [localized_candidate, english_candidate, original_candidate]
    elif variant == SearchVariant.ORIGINAL_TITLE:
        if original_title:
            candidates.append(original_title)
        elif cleaned_query:
            candidates.append(cleaned_query)
    elif variant == SearchVariant.ORIGINAL_TITLE_YEAR:
        if original_title and cleaned_year:
            candidates.append(f"{original_title} {cleaned_year}")
        elif original_title:
            candidates.append(original_title)
        elif cleaned_query and cleaned_year:
            candidates.append(f"{cleaned_query} {cleaned_year}")
        elif cleaned_query:
            candidates.append(cleaned_query)

    return _unique_title_candidates(candidates)


def _perform_search_with_title_fallback(
    indexer_key,
    dialog,
    query: str,
    ids: dict,
    mode: str,
    *args,
    variant: str = SearchVariant.DEFAULT,
    year: Optional[int] = None,
    title_language_mode: str = TITLE_LANGUAGE_LOCALIZED_FIRST,
    **kwargs,
):
    variant = _normalize_search_variant(variant)
    title_language_mode = _normalize_title_language_mode(title_language_mode)
    queries = _build_title_fallback_queries(
        query,
        ids,
        mode,
        variant,
        year,
        title_language_mode=title_language_mode,
    )

    for attempt, candidate in enumerate(queries, start=1):
        if attempt > 1:
            kodilog(
                f"Retrying {indexer_key} search with fallback title {candidate!r}",
                level=xbmc.LOGINFO,
            )

        results = _perform_search(
            indexer_key, dialog, candidate, mode, *args, variant=variant, year=year, **kwargs
        )
        if results:
            return results

    return []


def _handle_super_quick_play(params: dict) -> bool:
    if not get_setting("super_quick_play", False):
        kodilog("Super quick play disabled")
        return False

    ids = safe_json_loads(params.get("ids"))
    key = str(ids.get("original_id") or ids.get("imdb_id") or ids.get("tmdb_id") or "")

    if key:
        tv_data = safe_json_loads(params.get("tv_data") or "{}")
        if tv_data and "season" in tv_data and "episode" in tv_data:
            key += f'_{tv_data["season"]}_{tv_data["episode"]}'

    if not key:
        kodilog("Super quick play: No valid key found from ids")
        return False

    cached_torrent = cache.get(key)
    if not cached_torrent:
        kodilog("No cached media found")
        return False

    kodilog(f"Found cached media: {cached_torrent['title']}")

    if get_setting("silent_resume", False):
        playback_info = resolve_playback_url(cached_torrent)
        if not playback_info:
            notification(translation(90144))
            return True

        player = JacktookPLayer()
        player.run(data=playback_info)
        return True

    dialog = Dialog()
    if dialog.yesno(
        translation(90142),
        translation(90143),
    ):
        playback_info = resolve_playback_url(cached_torrent)
        if not playback_info:
            notification(translation(90144))
            return True

        player = JacktookPLayer()
        player.run(data=playback_info)
        return True

    kodilog("User chose not to play cached torrent")
    return False


def _process_search_results(
    results,
    mode,
    ep_name,
    episode,
    season,
    scoped_addon_url,
    query,
    media_type,
    rescrape,
):
    bypassed_streams = []
    other_results = results

    if get_setting("stremio_bypass_addons", True):
        bypass_list_str = str(get_setting("stremio_bypass_addon_list", "") or "")
        bypass_addons = [value.strip() for value in bypass_list_str.split(",") if value.strip()]

        def is_bypassed(result):
            if result.addonKey and result.addonKey in bypass_addons:
                return True

            legacy_name = (result.addonName or result.indexer or "").lower()
            return any(addon == legacy_name for addon in bypass_addons)

        bypassed_streams = [
            res
            for res in results
            if is_bypassed(res)
        ]
        other_results = [
            res
            for res in results
            if not is_bypassed(res)
        ]

    pre_results = []
    if other_results:
        pre_results = pre_process_results(
            other_results,
            mode,
            ep_name,
            episode,
            season,
            skip_episode_filter=bool(scoped_addon_url),
        )

    post_results = []
    if pre_results:
        post_results = process_results(
            pre_results, query, mode, media_type, rescrape, episode
        )

    # Combine results, prioritizing bypassed streams exact native sorting
    return bypassed_streams + post_results


def run_search_entry(params: dict):
    if _handle_super_quick_play(params):
        return

    query = params.get("query", "")
    mode = params.get("mode", "")
    media_type = params.get("media_type", "")
    ids = safe_json_loads(params.get("ids"))
    tv_data = normalize_tv_data(safe_json_loads(params.get("tv_data")))
    direct = params.get("direct", False)
    rescrape = params.get("rescrape", False)

    variant = _normalize_search_variant(params.get("search_variant", SearchVariant.DEFAULT))
    title_language_mode = _normalize_title_language_mode(
        params.get(
            "search_title_language_mode",
            get_setting("search_title_language_mode", TITLE_LANGUAGE_LOCALIZED_FIRST),
        )
    )
    year = params.get("year")
    if year is not None:
        try:
            year = int(year)
        except (ValueError, TypeError):
            year = None

    kodilog(
        f"run_search_entry received: query={query}, mode={mode}, media_type={media_type}, variant={variant}, title_language_mode={title_language_mode}, year={year}, rescrape={rescrape}, force_select={params.get('force_select', False)}"
    )

    library_data = None
    if params.get("stremio_addon_url") and params.get("stremio_catalog_type"):
        library_data = {
            "source": "stremio_catalog",
            "addon_url": params.get("stremio_addon_url"),
            "catalog_type": params.get("stremio_catalog_type"),
            "meta_id": params.get("stremio_meta_id") or ids.get("original_id", ""),
        }

    set_content_type(mode)
    set_watched_title(query, ids, mode, media_type=media_type, library_data=library_data)

    ep_name = tv_data.get("name", "")
    episode = tv_data.get("episode", 1)
    season = tv_data.get("season", 1)

    scoped_addon_url = params.get("scoped_addon_url", "")

    results = search_client(
        query,
        ids,
        mode,
        media_type,
        rescrape,
        season,
        episode,
        scoped_addon_url=scoped_addon_url,
        variant=variant,
        title_language_mode=title_language_mode,
        year=year,
    )
    if not results:
        notification("No results found")
        cancel_playback()
        return

    final_results = _process_search_results(
        results,
        mode,
        ep_name,
        episode,
        season,
        scoped_addon_url,
        query,
        media_type,
        rescrape,
    )

    if not final_results:
        notification(translation(90358))
        cancel_playback()
        return

    preferred_group = params.get("preferred_group")
    force_select = params.get("force_select", False)

    if auto_play_enabled() and not force_select:
        if not auto_play(final_results, ids, tv_data, mode, preferred_group):
            cancel_playback()
        return

    if not show_source_select(
        final_results,
        mode,
        ids,
        tv_data,
        query,
        media_type,
        rescrape,
        direct,
    ):
        cancel_playback()


def _perform_search(indexer_key, dialog, *args, **kwargs):
    show_dialog = kwargs.pop("show_dialog", True)
    scoped_addon_url = kwargs.pop("scoped_addon_url", "")

    if indexer_key == Indexer.STREMIO:
        if scoped_addon_url:
            addon = get_addon_by_base_url(scoped_addon_url)
            stremio_addons = [addon] if addon else []
        else:
            stremio_addons = get_selected_stream_addons()
        if not stremio_addons:
            notification("No Stremio addons selected")
            return []

        ids_dict = args[0]
        rest_args = args[1:]
        results = []

        for addon in stremio_addons:
            if show_dialog:
                update_dialog(addon.manifest.name, "Searching...", dialog)

            video_id = None
            original_id = ids_dict.get("original_id")
            media_kind = "series" if args[1] == "tv" or args[2] == "tv" else "movie"

            if original_id:
                prefix = original_id.split(":")[0]
                if addon.isSupported("stream", media_kind, prefix):
                    video_id = original_id

            # Try IMDb ID for addons that declare tt: prefix
            if not video_id and ids_dict.get("imdb_id"):
                if addon.isSupported("stream", media_kind, "tt"):
                    video_id = ids_dict.get("imdb_id")

            # Try TMDB ID for addons that declare tmdb: prefix
            if not video_id and ids_dict.get("tmdb_id"):
                if addon.isSupported("stream", media_kind, "tmdb:"):
                    video_id = f"tmdb:{ids_dict['tmdb_id']}"
                elif addon.isSupported("stream", media_kind, "tmdb"):
                    video_id = f"tmdb:{ids_dict['tmdb_id']}"

            if video_id:
                try:
                    client = StremioAddonClient(addon)
                    results.extend(client.search(video_id, *rest_args))
                except Exception as e:
                    kodilog(f"Error searching {addon.manifest.name}: {e}")

        return results

    client = get_client(indexer_key)
    if not client:
        return []

    if indexer_key == Indexer.BURST and not show_dialog:
        kwargs["silent"] = True

    return client.search(*args, **kwargs)


def _submit_search_tasks(
    executor,
    tasks,
    dialog,
    query,
    mode,
    media_type,
    season,
    episode,
    ids,
    scoped_addon_url,
    tmdb_id,
    imdb_id,
    show_dialog,
    variant: str = SearchVariant.DEFAULT,
    title_language_mode: str = TITLE_LANGUAGE_LOCALIZED_FIRST,
    year: Optional[int] = None,
):
    def submit_performer(*args, **kwargs):
        if "show_dialog" not in kwargs:
            kwargs["show_dialog"] = show_dialog
        if "scoped_addon_url" not in kwargs:
            kwargs["scoped_addon_url"] = scoped_addon_url
        if "variant" not in kwargs:
            kwargs["variant"] = variant
        if "title_language_mode" not in kwargs:
            kwargs["title_language_mode"] = title_language_mode
        if "year" not in kwargs:
            kwargs["year"] = year
        return executor.submit(
            _perform_search,
            *args,
            **kwargs,
        )

    if scoped_addon_url:
        if ids.get("imdb_id") or ids.get("original_id") or ids.get("tmdb_id"):
            tasks.append(
                submit_performer(
                    Indexer.STREMIO, dialog, ids, mode, media_type, season, episode
                )
            )
    else:
        add_task_if_enabled(
            executor,
            tasks,
            "easynews_enabled",
            Indexer.EASYNEWS,
            _perform_search_with_title_fallback,
            dialog,
            query,
            ids,
            mode,
            media_type,
            season,
            episode,
            show_dialog=show_dialog,
            scoped_addon_url=scoped_addon_url,
            variant=variant,
            title_language_mode=title_language_mode,
            year=year,
        )
        add_task_if_enabled(
            executor,
            tasks,
            "jacktookburst_enabled",
            Indexer.BURST,
            _perform_search,
            dialog,
            imdb_id,
            query,
            mode,
            media_type,
            season,
            episode,
            show_dialog=show_dialog,
            scoped_addon_url=scoped_addon_url,
        )
        if get_setting("prowlarr_enabled"):
            indexers_ids = get_setting("prowlarr_indexer_ids")
            tasks.append(
                executor.submit(
                    _perform_search_with_title_fallback,
                    Indexer.PROWLARR,
                    dialog,
                    query,
                    ids,
                    mode,
                    season,
                    episode,
                    indexers_ids,
                    show_dialog=show_dialog,
                    scoped_addon_url=scoped_addon_url,
                    variant=variant,
                    title_language_mode=title_language_mode,
                    year=year,
                )
            )
        add_task_if_enabled(
            executor,
            tasks,
            "jackett_enabled",
            Indexer.JACKETT,
            _perform_search_with_title_fallback,
            dialog,
            query,
            ids,
            mode,
            season,
            episode,
            show_dialog=show_dialog,
            scoped_addon_url=scoped_addon_url,
            variant=variant,
            title_language_mode=title_language_mode,
            year=year,
        )
        add_task_if_enabled(
            executor,
            tasks,
            "jackgram_enabled",
            Indexer.JACKGRAM,
            _perform_search,
            dialog,
            tmdb_id,
            query,
            mode,
            media_type,
            season,
            episode,
            show_dialog=show_dialog,
            scoped_addon_url=scoped_addon_url,
        )
        if get_setting("stremio_enabled") and (
            ids.get("imdb_id") or ids.get("original_id")
        ):
            tasks.append(
                submit_performer(
                    Indexer.STREMIO, dialog, ids, mode, media_type, season, episode
                )
            )


def _collect_search_results(tasks, listener, show_dialog) -> List[TorrentStream]:
    total_results = []
    total_tasks = len(tasks)
    completed_tasks = 0

    for future in as_completed(tasks):
        try:
            completed_tasks += 1
            if show_dialog and total_tasks > 0:
                percent = int(completed_tasks / total_tasks * 100)
                update_dialog(
                    "Searching", f"Searching... {percent}%", listener.dialog, percent
                )

            results = future.result()
            kodilog(f"Results from {future}: {results}", level=xbmc.LOGDEBUG)
            if results:
                total_results.extend(results)
        except Exception as e:
            import traceback

            error_details = traceback.format_exc()
            kodilog(
                f"Error resolving future result in thread pool: {e}\n{error_details}"
            )

    return total_results


def _submit_search_tasks_managed(
    manager,
    dialog,
    query,
    mode,
    media_type,
    season,
    episode,
    ids,
    scoped_addon_url,
    tmdb_id,
    imdb_id,
    variant: str = SearchVariant.DEFAULT,
    title_language_mode: str = TITLE_LANGUAGE_LOCALIZED_FIRST,
    year: Optional[int] = None,
):
    def submit_performer_managed(name, indexer_key, *args, **kwargs):
        kwargs["show_dialog"] = False
        if "scoped_addon_url" not in kwargs:
            kwargs["scoped_addon_url"] = scoped_addon_url
        if "variant" not in kwargs:
            kwargs["variant"] = variant
        if "title_language_mode" not in kwargs:
            kwargs["title_language_mode"] = title_language_mode
        if "year" not in kwargs:
            kwargs["year"] = year
        return manager.submit_task(
            name,
            indexer_key,
            _perform_search,
            indexer_key,
            *args,
            **kwargs,
        )

    if scoped_addon_url:
        addon = get_addon_by_base_url(scoped_addon_url)
        if addon and (
            ids.get("imdb_id") or ids.get("original_id") or ids.get("tmdb_id")
        ):
            submit_performer_managed(
                addon.manifest.name,
                Indexer.STREMIO,
                dialog,
                ids,
                mode,
                media_type,
                season,
                episode,
                scoped_addon_url=scoped_addon_url,
            )
    else:
        add_task_if_enabled_managed(
            manager,
            "easynews_enabled",
            Indexer.EASYNEWS,
            _perform_search_with_title_fallback,
            dialog,
            query,
            ids,
            mode,
            media_type,
            season,
            episode,
            show_dialog=False,
            scoped_addon_url=scoped_addon_url,
            variant=variant,
            title_language_mode=title_language_mode,
            year=year,
        )
        add_task_if_enabled_managed(
            manager,
            "jacktookburst_enabled",
            Indexer.BURST,
            _perform_search,
            dialog,
            imdb_id,
            query,
            mode,
            media_type,
            season,
            episode,
            show_dialog=False,
            scoped_addon_url=scoped_addon_url,
        )
        if get_setting("prowlarr_enabled"):
            indexers_ids = get_setting("prowlarr_indexer_ids")
            manager.submit_task(
                "Prowlarr",
                Indexer.PROWLARR,
                _perform_search_with_title_fallback,
                Indexer.PROWLARR,
                dialog,
                query,
                ids,
                mode,
                season,
                episode,
                indexers_ids,
                show_dialog=False,
                scoped_addon_url=scoped_addon_url,
                variant=variant,
                title_language_mode=title_language_mode,
                year=year,
            )
        add_task_if_enabled_managed(
            manager,
            "jackett_enabled",
            Indexer.JACKETT,
            _perform_search_with_title_fallback,
            dialog,
            query,
            ids,
            mode,
            season,
            episode,
            show_dialog=False,
            scoped_addon_url=scoped_addon_url,
            variant=variant,
            title_language_mode=title_language_mode,
            year=year,
        )
        add_task_if_enabled_managed(
            manager,
            "jackgram_enabled",
            Indexer.JACKGRAM,
            _perform_search,
            dialog,
            tmdb_id,
            query,
            mode,
            media_type,
            season,
            episode,
            show_dialog=False,
            scoped_addon_url=scoped_addon_url,
        )
        if get_setting("stremio_enabled") and (
            ids.get("imdb_id") or ids.get("original_id")
        ):
            stremio_addons = get_selected_stream_addons()
            for addon in stremio_addons:
                submit_performer_managed(
                    addon.manifest.name,
                    Indexer.STREMIO,
                    dialog,
                    ids,
                    mode,
                    media_type,
                    season,
                    episode,
                    scoped_addon_url=addon.url(),
                )


def search_client(
    query: str,
    ids: dict,
    mode: str,
    media_type: str,
    rescrape: bool,
    season: int,
    episode: int,
    show_dialog: bool = True,
    scoped_addon_url: str = "",
    variant: str = SearchVariant.DEFAULT,
    title_language_mode: str = TITLE_LANGUAGE_LOCALIZED_FIRST,
    year: Optional[int] = None,
) -> List[TorrentStream]:
    close_busy_dialog()

    if not rescrape:
        cached_results = get_cached_results(query, mode, media_type, episode)
        if cached_results:
            return cached_results

    tmdb_id, imdb_id = (ids.get("tmdb_id"), ids.get("imdb_id")) if ids else (None, None)
    total_results = []
    tasks = []

    use_detailed_status = show_dialog and get_setting("search_dialog_style", "0") == "1"

    if use_detailed_status:
        executor = ThreadPoolExecutor(max_workers=int(get_setting("thread_number", 6)))
        manager = SearchTaskManager(executor)
        _submit_search_tasks_managed(
            manager,
            None,
            query,
            mode,
            media_type,
            season,
            episode,
            ids,
            scoped_addon_url,
            tmdb_id,
            imdb_id,
            variant=variant,
            title_language_mode=title_language_mode,
            year=year,
        )

        item_info = {"ids": ids, "mode": mode}
        if ids:
            item_info.update(build_media_metadata(ids, mode))

        window = SearchStatusWindow(
            "search_status.xml",
            ADDON_PATH,
            task_manager=manager,
            item_information=item_info,
        )
        window.doModal()
        del window

        total_results = manager.collect_results()

        if manager.is_cancelled:
            executor.shutdown(wait=False)
        else:
            executor.shutdown(wait=False)
    else:
        with DialogListener() as listener:
            if show_dialog:
                listener.dialog.create("")

            with ThreadPoolExecutor(
                max_workers=int(get_setting("thread_number", 6))
            ) as executor:
                _submit_search_tasks(
                    executor,
                    tasks,
                    listener.dialog,
                    query,
                    mode,
                    media_type,
                    season,
                    episode,
                    ids,
                    scoped_addon_url,
                    tmdb_id,
                    imdb_id,
                    show_dialog,
                    variant=variant,
                    title_language_mode=title_language_mode,
                    year=year,
                )

                total_results = _collect_search_results(tasks, listener, show_dialog)

    cache_results(total_results, query, mode, media_type, episode)
    return total_results


def pre_process_results(
    results: List[TorrentStream],
    mode: str,
    ep_name: str,
    episode: int,
    season: int,
    skip_episode_filter: bool = False,
) -> List[TorrentStream]:
    return pre_process(results, mode, ep_name, episode, season, skip_episode_filter)


def process_results(
    pre_results: List[TorrentStream],
    query: str,
    mode: str,
    media_type: str,
    rescrape: bool,
    episode: int,
) -> List[TorrentStream]:
    torrent_results = []
    if get_setting("torrent_enable"):
        torrent_results = post_process(pre_results)
    close_busy_dialog()
    with DialogListener() as listener:
        debrid_results = check_debrid_cached(
            query, pre_results, mode, media_type, listener.dialog, rescrape, episode
        )
    return debrid_results + torrent_results


def show_source_select(
    results: List[TorrentStream],
    mode: str,
    ids: dict,
    tv_data: dict,
    query: str,
    media_type: str,
    rescrape: bool,
    direct: bool = False,
) -> bool:
    item_info = {
        "tv_data": tv_data,
        "ids": ids,
        "mode": mode,
        "query": query,
        "media_type": media_type,
        "rescrape": rescrape,
    }

    if not direct and ids:
        item_info.update(build_media_metadata(ids, mode))

    kodilog(
        f"show_source_select context: query={query}, mode={mode}, media_type={media_type}, year={item_info.get('year')}, ids={ids}"
    )

    xml_file_string = (
        "source_select_direct.xml" if mode == "direct" else "source_select.xml"
    )

    return source_select(item_info, xml_file=xml_file_string, sources=results)


def auto_play(
    results: List[TorrentStream],
    ids,
    tv_data,
    mode,
    preferred_group=None,
    force_select=False,
) -> bool:
    if force_select:
        return False

    filtered_results = clean_auto_play_undesired(results)
    if not filtered_results:
        notification("No suitable source found for auto play.")
        return False

    preferred_quality = str(get_setting("auto_play_quality"))
    quality_matches = [
        r for r in filtered_results if preferred_quality.lower() in r.quality.lower()
    ]

    if not quality_matches:
        notification("No sources found with the preferred quality.")
        return False

    selected_result = quality_matches[0]
    if preferred_group:
        group_matches = [
            r for r in quality_matches if preferred_group.lower() in r.title.lower()
        ]
        if group_matches:
            selected_result = group_matches[0]

    playback_info = resolve_playback_url(
        data={
            "title": selected_result.title,
            "mode": mode,
            "indexer": selected_result.indexer,
            "type": selected_result.type,
            "debrid_type": selected_result.debridType,
            "ids": ids,
            "info_hash": selected_result.infoHash,
            "url": selected_result.url,
            "tv_data": tv_data,
            "is_torrent": False,
        },
    )

    if not playback_info:
        return False

    player = JacktookPLayer()
    player.run(data=playback_info)
    del player
    return True


def stremio_addon_generator(stremio_addons, dialog, show_dialog):
    for addon in stremio_addons:
        if show_dialog:
            update_dialog(addon.manifest.name, "Searching...", dialog)
        yield StremioAddonClient(addon)


def add_task_if_enabled(
    executor, tasks, setting_key, indexer_key, perform_search, dialog, *args, **kwargs
):
    """Add a search task to the task list if the corresponding setting is enabled."""
    if get_setting(setting_key):
        tasks.append(
            executor.submit(perform_search, indexer_key, dialog, *args, **kwargs)
        )


def add_task_if_enabled_managed(
    manager, setting_key, indexer_key, perform_search, dialog, *args, **kwargs
):
    """Add a managed search task if the corresponding setting is enabled."""
    if get_setting(setting_key):
        name = str(indexer_key).title()
        manager.submit_task(
            name, indexer_key, perform_search, indexer_key, dialog, *args, **kwargs
        )
