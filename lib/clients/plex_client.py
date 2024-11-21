from lib.api.plex.media_server_api import convert_to_plex_id, get_media


class Plex:
    def __init__(self, discovery_url, auth_token, access_token, notification):
        self.discovery_url = discovery_url
        self.auth_token = auth_token
        self.access_token = access_token
        self._notification = notification

    def search(self, imdb_id, mode, media_type, season, episode):
        plex_id = convert_to_plex_id(
            url=self.discovery_url,
            access_token=self.access_token,
            auth_token=self.auth_token,
            id=imdb_id,
            mode=mode,
            media_type=media_type,
            season=season,
            episode=episode,
        )

        if not plex_id:
            return

        media = get_media(
            url=self.discovery_url,
            token=self.access_token,
            guid=plex_id,
        )

        streams = [meta.get_streams() for meta in media]
        return self.parse_response(streams)

    def parse_response(self, streams):
        results = []
        for stream in streams:
            for item in stream:
                results.append(
                    {
                        "title": item["title"],
                        "indexer": item["indexer"],
                        "downloadUrl": item["url"],
                        "publishDate": "",
                    }
                )
        return results
