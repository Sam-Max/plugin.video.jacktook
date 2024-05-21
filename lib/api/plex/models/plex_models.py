import os
from datetime import datetime
from enum import Enum
from urllib import parse
from lib.utils.kodi_utils import get_setting
from lib.utils.general_utils import Indexer


class AuthPin:
    def __init__(self, **kwargs):
        self.id = kwargs["id"]
        self.code = kwargs["code"]


class PlexUser:
    def __init__(self, **kwargs):
        self.username = kwargs["username"]
        self.thumb = kwargs["thumb"]


class PlexServer:
    def __init__(self, **kwargs):
        self.name = kwargs["name"]
        self.source_title = kwargs["sourceTitle"]
        self.public_address = kwargs["publicAddress"]
        self.access_token = kwargs["accessToken"]
        self.relay = kwargs["relay"]
        self.https_required = kwargs["httpsRequired"]
        self.connections = kwargs["connections"]


class PlexMediaType(str, Enum):
    show = "show"
    movie = "movie"
    episode = "episode"


class PlexLibrarySection:
    def __init__(self, **kwargs):
        self.key = kwargs.get("key")
        self.title = kwargs.get("title")
        self.type = kwargs.get("type")


class PlexMediaMeta:
    def __init__(self, **kwargs):
        self.guid = kwargs.get("guid")
        self.type = kwargs.get("type")
        self.title = kwargs.get("title")
        self.added_at = kwargs.get("addedAt")
        self.rating_key = kwargs.get("ratingKey", None)
        self.key = kwargs.get("key", None)
        self.studio = kwargs.get("studio", None)
        self.title_sort = kwargs.get("titleSort", None)
        self.library_section_title = kwargs.get("librarySectionTitle", None)
        self.library_sectionID = kwargs.get("librarySectionID", None)
        self.library_section_key = kwargs.get("librarySectionKey", None)
        self.content_rating = kwargs.get("contentRating", None)
        self.summary = kwargs.get("summary", "")
        self.rating = kwargs.get("rating", None)
        self.audience_rating = kwargs.get("audienceRating", None)
        self.year = kwargs.get("year", None)
        self.tagline = kwargs.get("tagline", None)
        self.thumb = kwargs.get("thumb", None)
        self.art = kwargs.get("art", None)
        self.duration = kwargs.get("duration", None)
        self.originally_available_at = kwargs.get("originallyAvailableAt", None)
        self.updated_at = kwargs.get("updatedAt", None)
        self.audience_rating_image = kwargs.get("audienceRatingImage", None)
        self.has_premium_primary_extra = kwargs.get("hasPremiumPrimaryExtra", None)
        self.rating_image = kwargs.get("ratingImage", None)
        self.media = kwargs.get("Media")
        self.genre = kwargs.get("Genre")
        self.country = kwargs.get("Country")
        self.guids = kwargs.get("Guid")
        self.director = kwargs.get("Director")
        self.writer = kwargs.get("Writer")
        self.role = kwargs.get("Role")
        self.producer = kwargs.get("Producer")

    def get_year(self):
        if self.year:
            return str(self.year)
        return datetime.fromtimestamp(self.added_at).strftime("%Y")

    def get_streams(self):
        streams = []
        for i, media in enumerate(self.media):
            name = f"{get_setting('plex_server_name')} {self.library_section_title}"
            filename = os.path.basename(media["Part"][0]["file"])
            audio_languages = set()
            subtitles_languages = set()
            for part_stream in media["Part"][0].get("Stream", []):
                if part_stream["streamType"] == 2:
                    audio_languages.add(part_stream.get("languageTag", "Unknown"))
                elif part_stream["streamType"] == 3:
                    subtitles_languages.add(part_stream.get("languageTag", "Unknown"))

            description_template = (
                f"{filename}\n"
                f'{"/".join(sorted(audio_languages))} '
                f'({"/".join(sorted(subtitles_languages))})'
            )
            
            encoded_params = parse.urlencode(
                {
                    "X-Plex-Token": get_setting("plex_server_token"),
                }
            )
            streams.append(
                {
                    "title": f"Direct Play - {name} - {description_template}",
                    "indexer": Indexer.PLEX,
                    "quality_description": f'Direct Play {media["videoResolution"]}',
                    "url": f"{get_setting('plex_streaming_url')}/{media['Part'][0]['key'][1:]}?{encoded_params}",
                }
            )

            encoded_params = parse.urlencode(
                {
                    "path": self.key,
                    "mediaIndex": i,
                    "protocol": "hls",
                    "fastSeek": 1,
                    "copyts": 1,
                    "autoAdjustQuality": 0,
                    "X-Plex-Platform": "Chrome",
                    "X-Plex-Token": get_setting("plex_server_token"),
                    "videoQuality": 100,
                }
            )
            streams.append(
                {
                    "title": f"Transcode - {name} - {description_template}",
                    "indexer": Indexer.PLEX,
                    "quality_description": f'Transcode {media["videoResolution"]} (original)',
                    "url": f"{get_setting('plex_streaming_url')}/video/:/transcode/universal/start.m3u8?{encoded_params}",
                }
            )

        return streams


class PlexEpisodeMeta:
    def __init__(self, **kwargs):
        self.guid = kwargs.get("guid")
        self.title = kwargs.get("title")
        self.index = kwargs.get("index")
        self.parent_index = kwargs.get("parentIndex")
        self.added_at = kwargs.get("addedAt")
        self.type = kwargs.get("type")
        self.rating_key = kwargs.get("ratingKey")
        self.key = kwargs.get("key")
        self.parent_rating_key = kwargs.get("parentRatingKey")
        self.grandparent_rating_key = kwargs.get("grandparentRatingKey")
        self.studio = kwargs.get("studio")
        self.grandparent_key = kwargs.get("grandparentKey")
        self.parent_key = kwargs.get("parentKey")
        self.grandparent_title = kwargs.get("grandparentTitle")
        self.parent_title = kwargs.get("parentTitle")
        self.content_rating = kwargs.get("contentRating")
        self.summary = kwargs.get("summary", "")
        self.year = kwargs.get("year")
        self.thumb = kwargs.get("thumb")
        self.art = kwargs.get("art")
        self.parent_thumb = kwargs.get("parentThumb")
        self.grandparent_thumb = kwargs.get("grandparentThumb")
        self.grandparent_art = kwargs.get("grandparentArt")
        self.grandparent_theme = kwargs.get("grandparentTheme")
        self.duration = kwargs.get("duration")
        self.originally_available_at = kwargs.get("originallyAvailableAt")
        self.updated_at = kwargs.get("updatedAt")
        self.media = kwargs.get("media", [])
