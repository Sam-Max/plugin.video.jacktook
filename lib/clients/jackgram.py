import json
from requests import Session
from lib.api.jacktook.kodi import kodilog
from lib.utils.kodi_utils import convert_size_to_bytes, translation


class Jackgram:
    def __init__(self, host, notification):
        self.host = host.rstrip("/")
        self._notification = notification
        self.session = Session()

    def search(self, tmdb_id, query, mode, media_type, season, episode):
        try:
            if mode == "tv" or media_type == "tv":
                url = f"{self.host}/stream/series/{tmdb_id}:{season}:{episode}.json"
            elif mode == "movies" or media_type == "movies":
                url = f"{self.host}/stream/movie/{tmdb_id}.json"
            else:
                url = f"{self.host}/search?query={query}"

            res = self.session.get(url, timeout=10)
            if res.status_code != 200:
                return
            return self.parse_response(res, mode)
        except Exception as e:
            self._notification(f"{translation(30228)}: {str(e)}")

    def parse_response(self, res, mode):
        res = json.loads(res.text)
        if mode in ["tv", "movies"]:
            results = []
            for item in res["streams"]:
                link = self.generate_link(tmdb_id=res["tmdb_id"], hash=item["hash"])
                results.append(
                    {
                        "indexer": item["name"],
                        "title": item["title"],
                        "qualityTitle": item["quality"],
                        "size": item["size"],
                        "publishDate": item["date"],
                        "duration": item["duration"],
                        "downloadUrl": link,
                    }
                )
            return results
        else:
            results = []
            for item in res["results"]:
                for file in item["files"]:
                    link = self.generate_link(
                        tmdb_id=item["tmdb_id"], hash=file["hash"]
                    )
                    results.append(
                        {
                            "indexer": file["name"],
                            "title": file["title"],
                            "qualityTitle": file["quality"],
                            "size": file["size"],
                            "publishDate": file["date"],
                            "duration": file["duration"],
                            "downloadUrl": link,
                        }
                    )
                return results

    def generate_link(self, tmdb_id, hash):
        return f"{self.host}/dl/{tmdb_id}?hash={hash}"
