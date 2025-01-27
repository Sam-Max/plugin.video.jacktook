import json
import logging
from types import SimpleNamespace
from requests import ConnectTimeout, ReadTimeout
from requests.exceptions import RequestException
from lib.clients.base import BaseClient
from lib.utils.utils import USER_AGENT_HEADER, info_hash_to_magnet


class Zilean(BaseClient):
    def __init__(self, host, timeout, notification):
        super().__init__(host, notification)
        self.timeout = timeout
        self.initialized = self.validate()
        if not self.initialized:
            return

    def validate(self) -> bool:
        try:
            response = self.ping()
            return response.ok
        except Exception as e:
            self._notification(f"Zilean failed to initialize: {e}")
            return False

    def search(self, query, mode, media_type, season, episode):
        try:
            data = self.api_scrape(query, mode, media_type, season, episode)
            return self.parse_response(data)
        except RateLimitExceeded:
            logging.warning(f"Zilean ratelimit exceeded for query: {query}")
        except ConnectTimeout:
            logging.warning(f"Zilean connection timeout for query: {query}")
        except ReadTimeout:
            logging.warning(f"Zilean read timeout for query: {query}")
        except RequestException as e:
            logging.error(f"Zilean request exception: {e}")
        except Exception as e:
            logging.error(f"Zilean exception thrown: {e}")

    def api_scrape(self, query, mode, media_type, season, episode):
        filtered_url = f"{self.host}/dmm/filtered"
        search_url = f"{self.host}/dmm/search"

        if mode in {"tv", "movies"} or media_type in {"tv", "movies"}:
            params = {"Query": query}
            if mode == "tv" or media_type == "tv":
                params.update({"Season": season, "Episode": episode})

            res = self.session.get(
                filtered_url, params=params, headers=USER_AGENT_HEADER, timeout=10
            )
        else:
            payload = {"queryText": query}
            res = self.session.post(
                search_url,
                json=payload,
                headers=USER_AGENT_HEADER,
                timeout=self.timeout,
            )

        if res.status_code != 200:
            return

        response = json.loads(
            res.content, object_hook=lambda item: SimpleNamespace(**item)
        )

        torrents = []
        for result in response:
            torrents.append(
                {
                    "infoHash": result.info_hash,
                    "filename": result.raw_title,
                    "filesize": result.size,
                    "languages": result.languages,
                }
            )

        return torrents

    def parse_response(self, data):
        results = []
        for item in data:
            results.append(
                {
                    "title": item["filename"],
                    "type": "Torrent",
                    "indexer": "Zilean",
                    "guid": item["infoHash"],
                    "magnet": info_hash_to_magnet(item["infoHash"]),
                    "infoHash": item["infoHash"],
                    "size": item["filesize"],
                    "seeders": 0,
                    "languages": item["languages"],
                    "fullLanguages": "",
                    "publishDate": "",
                    "peers": 0,
                }
            )
        return results

    def ping(self, additional_headers=None):
        return self.session.get(
            f"{self.host}/healthchecks/ping",
            headers=additional_headers,
            timeout=self.timeout,
        )


class RateLimitExceeded(Exception):
    pass
