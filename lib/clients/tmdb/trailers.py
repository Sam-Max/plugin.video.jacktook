import os
from typing import Iterable, Optional

from lib.api.tmdbv3api.objs.movie import Movie
from lib.api.tmdbv3api.objs.tv import TV
from lib.utils.kodi.utils import kodilog


YOUTUBE_WATCH_URL = "https://www.youtube.com/watch?v={}"


def _normalize_media_type(media_type: Optional[str]) -> Optional[str]:
    if not media_type:
        return None

    normalized = str(media_type).strip().lower()
    if normalized in ("movie", "movies"):
        return "movie"
    if normalized in ("tv", "show", "shows", "series"):
        return "tv"
    return None


def choose_tmdb_trailer(videos: Optional[Iterable[dict]]) -> Optional[dict]:
    candidates = []
    for index, video in enumerate(videos or []):
        if (video.get("site") or "") != "YouTube":
            continue

        trailer_type = (video.get("type") or "").strip().lower()
        if trailer_type == "trailer":
            type_rank = 0
        elif trailer_type == "teaser":
            type_rank = 1
        elif trailer_type == "clip":
            type_rank = 2
        else:
            continue

        yt_id = video.get("key")
        if not yt_id:
            continue

        candidates.append(
            (
                type_rank,
                0 if bool(video.get("official")) else 1,
                index,
                yt_id,
            )
        )

    if not candidates:
        return None

    _, _, _, yt_id = min(candidates)
    return {
        "yt_id": yt_id,
        "youtube_url": YOUTUBE_WATCH_URL.format(yt_id),
    }


def _normalize_videos(videos):
    if videos is None:
        return []
    if isinstance(videos, dict):
        return videos.get("results") or []

    results = getattr(videos, "results", None)
    if results is not None:
        return list(results)

    return list(videos)


def _tmdb_language_attempts():
    current = os.environ.get("TMDB_LANGUAGE") or "en-US"
    attempts = []

    def add(language, include_video_language=None):
        candidate = (language, include_video_language)
        if candidate not in attempts:
            attempts.append(candidate)

    add(current, f"{current},null")
    add("en-US", "en-US,null")
    add(current, None)
    add("en-US", None)
    return attempts


def resolve_tmdb_trailer(tmdb_id, media_type: Optional[str]) -> Optional[dict]:
    normalized_media_type = _normalize_media_type(media_type)
    if not tmdb_id or not normalized_media_type:
        kodilog(
            f"Trailer/TMDB: skipped lookup tmdb_id={tmdb_id!r} media_type={media_type!r} normalized={normalized_media_type!r}"
        )
        return None

    trailer = None
    last_error = None

    for language, include_video_language in _tmdb_language_attempts():
        try:
            if normalized_media_type == "movie":
                client = Movie()
                client.language = language
                videos = client.videos(tmdb_id, page=1)
            else:
                client = TV()
                client.language = language
                videos = client.videos(
                    tmdb_id,
                    include_video_language=include_video_language,
                    page=1,
                )
        except Exception as exc:
            last_error = exc
            continue

        videos = _normalize_videos(videos)
        trailer = choose_tmdb_trailer(videos)
        if trailer:
            break

    if last_error and not trailer:
        kodilog(
            f"Trailer/TMDB: lookup failed tmdb_id={tmdb_id!r} media_type={normalized_media_type!r} error={last_error}"
        )

    if not trailer:
        kodilog(
            f"Trailer/TMDB: no youtube trailer found tmdb_id={tmdb_id!r} media_type={normalized_media_type!r}"
        )
        return None

    kodilog(
        f"Trailer/TMDB: selected yt_id={trailer.get('yt_id')!r} tmdb_id={tmdb_id!r} media_type={normalized_media_type!r}"
    )
    return trailer
