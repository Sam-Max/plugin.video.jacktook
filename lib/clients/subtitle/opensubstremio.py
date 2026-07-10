import contextlib
import os
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests
import xbmc
import xbmcgui

from lib.clients.subtitle.utils import (
    get_language_code,
    language_code_to_name,
    slugify_title,
)
from lib.utils.general.utils import USER_AGENT_HEADER
from lib.utils.kodi.settings import get_int_setting, subtitle_automation_enabled
from lib.utils.kodi.utils import (
    ADDON_PROFILE_PATH,
    get_setting,
    kodilog,
    set_setting,
    translation,
)

SUBTITLE_EXTENSIONS = {".srt", ".vtt", ".ass", ".ssa", ".sub", ".txt"}
DEFAULT_ENDPOINT_TIMEOUT = 10
AUTO_SELECT_ENDPOINT_TIMEOUT = 5
DEFAULT_DOWNLOAD_TIMEOUT = 15
AUTO_SELECT_DOWNLOAD_TIMEOUT = 5


class OpenSubtitleStremioClient:
    def __init__(self, notification: Callable[[str], None]):
        self.notification = notification

    @staticmethod
    def _build_url(
        base_url: str,
        mode: str,
        imdb_id: str,
        season: Optional[int] = None,
        episode: Optional[int] = None,
    ) -> str:
        """Build a subtitles endpoint URL from a (possibly trailing-slashed) base.

        Ensures exactly one ``/`` separates the base from ``subtitles/...``,
        regardless of whether the caller passed a trailing slash. ``base_url``
        is expected to come from :func:`build_addon_base_url` (which strips
        the trailing slash) or :func:`normalize_transport_url`.
        """
        base = (base_url or "").rstrip("/") + "/"
        if mode == "tv":
            return f"{base}subtitles/series/{imdb_id}:{season}:{episode}.json"
        return f"{base}subtitles/movie/{imdb_id}.json"

    def _fetch_subtitles_data_for_source(
        self,
        base_url: str,
        mode: str,
        imdb_id: str,
        season: Optional[int] = None,
        episode: Optional[int] = None,
        timeout: int = DEFAULT_ENDPOINT_TIMEOUT,
        max_retries: int = 2,
        retry_delay: float = 1.0,
    ) -> Optional[List[Dict[str, Any]]]:
        """Fetch subtitles from a single addon's base URL.

        Returns:
            - list (possibly empty) on HTTP 200 with a valid JSON body
            - ``None`` on non-200, network error, or non-JSON response
        """
        url = self._build_url(base_url, mode, imdb_id, season, episode)
        for attempt in range(max_retries + 1):
            try:
                response = requests.get(url, timeout=timeout)
            except Exception as e:
                if attempt < max_retries:
                    kodilog(
                        f"[StremioSubs] addon {base_url} failed (attempt {attempt + 1}/{max_retries + 1}), retrying: {e}",  # noqa: E501
                        level=xbmc.LOGWARNING,
                    )
                    time.sleep(retry_delay)
                    continue
                kodilog(
                    f"[StremioSubs] addon {base_url} failed after {max_retries + 1} attempts: {e}",
                    level=xbmc.LOGWARNING,
                )
                return None
            if response.status_code != 200:
                if 400 <= response.status_code < 500:
                    kodilog(
                        f"[StremioSubs] addon {base_url} failed: HTTP {response.status_code}",
                        level=xbmc.LOGWARNING,
                    )
                    return None
                if attempt < max_retries:
                    kodilog(
                        f"[StremioSubs] addon {base_url} failed (attempt {attempt + 1}/{max_retries + 1}), retrying: HTTP {response.status_code}",  # noqa: E501
                        level=xbmc.LOGWARNING,
                    )
                    time.sleep(retry_delay)
                    continue
                kodilog(
                    f"[StremioSubs] addon {base_url} failed after {max_retries + 1} attempts: HTTP {response.status_code}",  # noqa: E501
                    level=xbmc.LOGWARNING,
                )
                return None
            try:
                data = response.json()
            except Exception as e:
                kodilog(
                    f"[StremioSubs] addon {base_url} failed: invalid JSON ({e})",
                    level=xbmc.LOGWARNING,
                )
                return None
            kodilog(
                f"[StremioSubs] subtitles response: {data}",
                level=xbmc.LOGDEBUG,
            )
            if not isinstance(data, dict):
                return []
            return data.get("subtitles") or []
        return None

    @staticmethod
    def _id_prefix(imdb_id: str) -> str:
        """Extract the id prefix used by ``Addon.isSupported``.

        ``tt0111161`` -> ``"tt"`` ; ``kitsu:1`` -> ``"kitsu"``.
        Strips the ``:<suffix>`` if present, then strips trailing digits so
        numeric imdb ids map to their alphabetic prefix.
        """
        if not imdb_id:
            return ""
        head = str(imdb_id).split(":", 1)[0]
        # Strip trailing digits: "tt0111161" -> "tt", "kitsu" -> "kitsu".
        stripped = head.rstrip("0123456789")
        return stripped or head

    def _resolve_legacy_migration(self, selected_keys: List[str]) -> Optional[Tuple[str, str]]:
        """One-time legacy host migration (T6 / F5).

        Returns a ``(pseudo_key, base_url)`` tuple if the legacy
        ``stremio_sub_addon_host`` should be queried as a pseudo-source
        for this lookup, otherwise ``None``. Writes the
        ``stremio_subtitle_addons_migrated`` memento on first use so
        subsequent calls return ``None``.
        """
        try:
            from lib.api.stremio.addon_manager import normalize_transport_url
        except Exception:
            normalize_transport_url = None  # type: ignore[assignment]

        try:
            migrated = bool(get_setting("stremio_subtitle_addons_migrated", False))
        except Exception:
            migrated = False

        if migrated:
            return None
        if selected_keys:
            # Selection present (even if only legacy->new keys were migrated);
            # do not auto-inject legacy.
            return None
        try:
            legacy_raw = str(get_setting("stremio_sub_addon_host", "") or "").strip()
        except Exception:
            legacy_raw = ""
        if not legacy_raw:
            return None
        if normalize_transport_url is not None:
            try:
                legacy_host = normalize_transport_url(legacy_raw)
            except Exception:
                legacy_host = legacy_raw
        else:
            legacy_host = legacy_raw
        if not legacy_host:
            return None
        with contextlib.suppress(Exception):
            set_setting("stremio_subtitle_addons_migrated", True)
        kodilog(
            "[StremioSubs] legacy host migrated (one-time)",
            level=xbmc.LOGINFO,
        )
        return (f"legacy|{legacy_host}", legacy_host)

    def get_subtitles(
        self,
        mode: str,
        imdb_id: str,
        season: Optional[int] = None,
        episode: Optional[int] = None,
        auto_select: bool = False,
        addon_manager: Optional[Any] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        """Resolve subtitles from all selected Stremio addons (multi-source).

        Flow:
            1. Read ``stremio_subtitle_addons`` (CSV of addon instance keys).
            2. Run one-time legacy migration (T6) if applicable.
            3. Resolve each key -> live ``Addon`` via ``AddonManager``.
            4. Filter by ``addon.isSupported("subtitles", type, id_prefix)``.
            5. Sequential query each accepted addon's ``addon.url()`` in
               selection order; cap by elapsed time under auto_select (F6).
            6. Merge + dedup by ``url`` else ``"{sub_id}|{lang}"`` (F4/EC5).
            7. Apply language filter (F8).
        """
        # 1. Read selection (CSV of addon instance keys).
        try:
            raw_selection = str(get_setting("stremio_subtitle_addons", "") or "").strip()
        except Exception:
            raw_selection = ""
        selected_keys: List[str] = [k.strip() for k in raw_selection.split(",") if k.strip()]

        # 2. One-time legacy migration (T6 / F5).
        legacy = self._resolve_legacy_migration(selected_keys)
        if legacy is not None:
            legacy_key, legacy_base = legacy
            # Prepend legacy to selection for this lookup only; selected_keys
            # intentionally NOT mutated so future reads see only user picks.
            ordered_sources: List[Tuple[str, str]] = [(legacy_key, legacy_base)]
            for k in selected_keys:
                ordered_sources.append((k, ""))
        else:
            ordered_sources = [(k, "") for k in selected_keys]

        # EC4: no source at all -> silent skip, caller treats as no result.
        if not ordered_sources:
            return None

        # 3. Resolve addons. Defer get_addons() until we actually need it,
        # so legacy-only lookups don't trigger the live catalog fetch.
        resolved: List[Tuple[str, str, str]] = []  # (source_key, base_url, display_label)
        id_prefix = self._id_prefix(imdb_id)
        video_type = "series" if mode == "tv" else "movie"
        live_manager: Optional[Any] = addon_manager
        for source_key, base_url_hint in ordered_sources:
            if base_url_hint:
                # Legacy pseudo-source: no resolution needed.
                resolved.append((source_key, base_url_hint, "Legacy subtitle addon"))
                continue
            if live_manager is None:
                try:
                    from lib.clients.stremio.helpers import get_addons

                    live_manager = get_addons()
                except Exception as e:
                    kodilog(
                        f"[StremioSubs] external lookup skipped: no addons "
                        f"resolved and none selected ({e})",
                        level=xbmc.LOGDEBUG,
                    )
                    break
                if live_manager is None or not getattr(live_manager, "addons", None):
                    kodilog(
                        "[StremioSubs] external lookup skipped: no addons "
                        "resolved and none selected",
                        level=xbmc.LOGDEBUG,
                    )
                    break
            try:
                addon = live_manager.get_addon_by_key(source_key)
            except Exception:
                addon = None
            if addon is None:
                kodilog(
                    f"[StremioSubs] addon {source_key} skipped: not installed",
                    level=xbmc.LOGDEBUG,
                )
                continue
            if id_prefix and not addon.isSupported("subtitles", video_type, id_prefix):
                kodilog(
                    f"[StremioSubs] addon {source_key} skipped: idPrefix {id_prefix} not supported",
                    level=xbmc.LOGDEBUG,
                )
                continue
            try:
                base_url = addon.url()
            except Exception:
                base_url = ""
            if not base_url:
                kodilog(
                    f"[StremioSubs] addon {source_key} skipped: empty base url",
                    level=xbmc.LOGDEBUG,
                )
                continue
            try:
                source_label = addon.label()
            except Exception:
                source_label = getattr(getattr(addon, "manifest", None), "name", "") or source_key
            resolved.append((source_key, base_url, source_label))

        if not resolved:
            kodilog(
                "[StremioSubs] external lookup skipped: no addons resolved and none selected",
                level=xbmc.LOGDEBUG,
            )
            return None

        # 4-5. Sequential per-source query, respecting auto-select cap.
        per_call_timeout = get_int_setting("stremio_timeout") or DEFAULT_ENDPOINT_TIMEOUT
        if auto_select:
            per_call_timeout = min(per_call_timeout, AUTO_SELECT_ENDPOINT_TIMEOUT)
        cap_seconds = AUTO_SELECT_ENDPOINT_TIMEOUT if auto_select else None
        start = time.monotonic()
        merged: List[Dict[str, Any]] = []
        merged_source_labels: List[str] = []
        seen_keys: set = set()
        queried = 0
        failed = 0
        sources_with_subs = 0
        dup_count = 0
        dup_key_kind = "url"
        cap_broken = False
        for source_key, base_url, source_label in resolved:
            if cap_seconds is not None and (time.monotonic() - start) >= cap_seconds:
                remaining = len(resolved) - queried
                kodilog(
                    f"[StremioSubs] autoplay timeout cap reached after "
                    f"{round(time.monotonic() - start, 2)}s, skipping remaining "
                    f"{remaining} addon(s)",
                    level=xbmc.LOGINFO,
                )
                cap_broken = True
                break
            queried += 1
            result = self._fetch_subtitles_data_for_source(
                base_url, mode, imdb_id, season, episode, timeout=per_call_timeout
            )
            if result is None:
                failed += 1
                continue
            if not result:
                kodilog(
                    f"[StremioSubs] addon {source_key} returned 0 subs (200 empty)",
                    level=xbmc.LOGDEBUG,
                )
                continue
            sources_with_subs += 1
            for sub in result:
                if not isinstance(sub, dict):
                    continue
                sub_id = sub.get("id") or sub.get("subId") or ""
                sub_lang = sub.get("lang") or ""
                sub_url = sub.get("url") or ""
                if sub_url:
                    key = sub_url
                    kind = "url"
                elif sub_id:
                    key = f"{sub_id}|{sub_lang}"
                    kind = "sub_id|lang"
                else:
                    # No usable key - keep but mark with a synthetic unique key
                    # so we still preserve the entry without collapsing siblings.
                    key = f"_anon|{id(sub)}"
                    kind = "anon"
                if key in seen_keys:
                    dup_count += 1
                    dup_key_kind = kind
                    continue
                seen_keys.add(key)
                merged.append(sub)
                merged_source_labels.append(source_label)

        # 6. Dedup summary.
        if dup_count:
            kodilog(
                f"[StremioSubs] dedup: {dup_count} duplicate(s) removed (key={dup_key_kind})",
                level=xbmc.LOGDEBUG,
            )

        kodilog(
            f"[StremioSubs] external lookup: queried {queried} addon(s), "
            f"{sources_with_subs} returned {len(merged)} subs total, "
            f"{failed} failed",
            level=xbmc.LOGINFO,
        )

        if cap_broken and not merged:
            return None
        if not merged:
            return None

        # 7. Language filter (F8) - applies AFTER merge+dedup.
        try:
            sub_language = get_setting("subtitle_language")
            subtitle_automation = subtitle_automation_enabled()
        except Exception:
            sub_language = None
            subtitle_automation = False
        if auto_select or subtitle_automation:
            target_lang = get_language_code(sub_language) if sub_language else ""
            filtered = [s for s in merged if s.get("lang") == target_lang]
            if filtered:
                return filtered
            return []

        # 8. Manual multiselect.
        items = [
            xbmcgui.ListItem(
                label=(f"{translation(90665) % i} — {source_label or 'Stremio subtitle addon'}"),
                label2=language_code_to_name(s.get("lang") or ""),
            )
            for i, (s, source_label) in enumerate(zip(merged, merged_source_labels))
        ]
        dialog = xbmcgui.Dialog()
        selected_indices = dialog.multiselect(
            translation(90256),
            items,
            useDetails=True,
        )
        if selected_indices is None:
            return []
        return [merged[i] for i in selected_indices]

    def select_subtitles(
        self,
        subtitles: List[Dict[str, Any]],
        auto_select: bool = False,
    ) -> Optional[List[Dict[str, Any]]]:
        kodilog(
            f"[StremioSubs] select_subtitles input: {len(subtitles)} candidate(s), "
            f"auto_select={auto_select}",
            level=xbmc.LOGINFO,
        )
        kept = [s for s in subtitles if s.get("url")]
        kodilog(
            f"[StremioSubs] {len(kept)}/{len(subtitles)} candidate(s) kept after url-filter",
            level=xbmc.LOGDEBUG,
        )
        subtitles = kept
        if not subtitles:
            kodilog(
                "[StremioSubs] select_subtitles: no embedded subtitles with a "
                "downloadable url -> returning None (caller will try endpoint)",
                level=xbmc.LOGINFO,
            )
            return

        sub_language = get_setting("subtitle_language")
        if auto_select or subtitle_automation_enabled():
            target_lang = get_language_code(sub_language)
            filtered = [s for s in subtitles if s.get("lang") == target_lang]
            kodilog(
                f"[StremioSubs] auto-download: {len(filtered)}/{len(subtitles)} "
                f"embedded subtitle(s) match configured language '{sub_language}' "
                f"(code={target_lang})",
                level=xbmc.LOGINFO,
            )
            if filtered:
                return filtered
            return []

        items = [
            xbmcgui.ListItem(
                label=f"{translation(90665) % i} — Embedded stream subtitle",
                label2=language_code_to_name(s.get("lang") or ""),
            )
            for i, s in enumerate(subtitles)
        ]

        kodilog(
            f"[StremioSubs] opening multiselect dialog with {len(items)} "
            f"embedded subtitle option(s)",
            level=xbmc.LOGINFO,
        )
        selected_indices = xbmcgui.Dialog().multiselect(
            translation(90256),
            items,
            useDetails=True,
        )
        if selected_indices is None:
            kodilog(
                "[StremioSubs] user cancelled the embedded subtitle multiselect "
                "dialog -> returning [] (endpoint NOT tried)",
                level=xbmc.LOGINFO,
            )
            return []
        kodilog(
            f"[StremioSubs] user selected {len(selected_indices)} embedded subtitle(s)",
            level=xbmc.LOGINFO,
        )
        return [subtitles[i] for i in selected_indices]

    def _get_subtitle_extension(self, url: str) -> str:
        extension = os.path.splitext(urlparse(url).path)[1].lower()
        return extension if extension in SUBTITLE_EXTENSIONS else ".srt"

    def download_subtitles_batch(
        self,
        subtitles: List[Dict[str, Any]],
        imdb_id: str,
        title: str,
        season: Optional[int] = None,
        episode: Optional[int] = None,
        folder_path: Optional[str] = None,
        auto_select: bool = False,
    ) -> List[str]:
        kodilog(
            f"[StremioSubs] download_subtitles_batch: {len(subtitles)} subtitle(s), "
            f"auto_select={auto_select}, timeout="
            f"{AUTO_SELECT_DOWNLOAD_TIMEOUT if auto_select else DEFAULT_DOWNLOAD_TIMEOUT}s",
            level=xbmc.LOGINFO,
        )
        file_paths = []
        timeout = AUTO_SELECT_DOWNLOAD_TIMEOUT if auto_select else DEFAULT_DOWNLOAD_TIMEOUT
        failed = 0
        for idx, subtitle in enumerate(subtitles):
            try:
                kodilog(
                    f"[StremioSubs] downloading embedded subtitle #{idx} "
                    f"lang={subtitle.get('lang') or '?'} url={subtitle.get('url', '')[:80]}",
                    level=xbmc.LOGDEBUG,
                )
                file_path = self.download_subtitle(
                    subtitle, idx, imdb_id, title, season, episode, folder_path, timeout=timeout
                )
                if file_path:
                    file_paths.append(file_path)
                else:
                    failed += 1
            except Exception as e:
                failed += 1
                kodilog(f"[StremioSubs] failed to download embedded subtitle #{idx}: {e}")
                continue
        kodilog(
            f"[StremioSubs] download_subtitles_batch done: {len(file_paths)} ok, "
            f"{failed} failed of {len(subtitles)}",
            level=xbmc.LOGINFO,
        )
        return file_paths

    def download_subtitle(
        self,
        subtitle: Dict[str, Any],
        index: int,
        imdb_id: str,
        title: str,
        season: Optional[int] = None,
        episode: Optional[int] = None,
        folder_path: Optional[str] = None,
        timeout: int = DEFAULT_DOWNLOAD_TIMEOUT,
    ) -> Optional[str]:
        url = subtitle.get("url", "")
        lang = subtitle.get("lang") or ""
        lang_name = language_code_to_name(lang)
        lang_name = slugify_title(lang_name) or "unknown"
        extension = self._get_subtitle_extension(url)

        title = slugify_title(title)

        if folder_path:
            filename = f"Subtitle No.{index}.{title}.{lang_name}{extension}"
            file_path = os.path.join(folder_path, filename)
        else:
            base_path = os.path.join(ADDON_PROFILE_PATH, "Subtitles", imdb_id)
            if season and episode:
                file_path = os.path.join(
                    base_path,
                    str(season),
                    str(episode),
                    f"Subtitle No.{index}.{title}.S{season}E{episode}.{lang_name}{extension}",
                )
            elif season:
                file_path = os.path.join(
                    base_path,
                    str(season),
                    f"Subtitle No.{index}.{title}.S{season}.{lang_name}{extension}",
                )
            else:
                filename = f"Subtitle No.{index}.{title}.{lang_name}{extension}"
                file_path = os.path.join(base_path, filename)

        try:
            response = None
            for attempt in range(3):  # 1 initial + 2 retries
                try:
                    response = requests.get(
                        url, stream=True, headers=USER_AGENT_HEADER, timeout=timeout
                    )
                except Exception:
                    if attempt < 2:
                        time.sleep(1.0)
                        continue
                    raise
                if response.status_code == 200:
                    break
                if attempt < 2:
                    time.sleep(1.0)
                    continue
                self.notification(f"Failed to download {url}, status code {response.status_code}")
                raise Exception(f"HTTP {response.status_code}")
            with open(file_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file.write(chunk)
            return file_path
        except Exception as e:
            kodilog(f"Subtitle download error for {url}: {e}")
            self.notification(f"Subtitle download error for {url}: {e}")
            raise
