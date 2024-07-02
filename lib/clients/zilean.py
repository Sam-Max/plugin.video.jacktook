import json
import logging
from types import SimpleNamespace
from typing import Dict, List, Any
from requests import ConnectTimeout, ReadTimeout, Session
from requests.exceptions import RequestException


# Source: https://rivenmedia/riven/backend/program/scrapers/zilean.py
# With some modifications from source


class Zilean:
    def __init__(self, url, timeout, notification, logger):
        self.api_key = None
        self.url = url
        self.timeout = timeout
        self.session = Session()
        self._notification = notification
        self.initialized = self.validate()
        self.logger = logger
        if not self.initialized:
            return

    def validate(self) -> bool:
        try:
            response = self.ping()
            return response.ok
        except Exception as e:
            self._notification(f"Zilean failed to initialize: {e}")
            return False

    def search(self, query) -> Dict[str, str]:
        if not query:
            return {}

        try:
            data = self.scrape(query)
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
        return {}

    def scrape(self, query) -> List[Dict[str, Any]]:
        data, item_count = self.api_scrape(query)
        if data:
            logging.info(
                "SCRAPER", f"Found {len(data)} entries out of {item_count} for {query}"
            )
        else:
            logging.info("NOT_FOUND", f"No entries found for {query}")
        return data 
    
    def api_scrape(self, query) -> tuple[Dict[str, str], int]:
        query_text = query
        if not query_text:
            return {}, 0

        url = f"{self.url}/dmm/search"
        payload = {"queryText": query_text}

        response = self.session.post(url, json=payload, timeout=self.timeout)
        if response.status_code != 200:
            return {}, 0
        response = json.loads(
            response.content, object_hook=lambda item: SimpleNamespace(**item)
        )

        torrents = []
        for result in response:
            if not result.filename or not result.infoHash:
                continue
            torrents.append(
                {
                    "infoHash": result.infoHash,
                    "filename": result.filename,
                    "filesize": result.filesize,
                }
            )

        return torrents, len(torrents)

    def parse_response(self, data):
        results = []
        for item in data:
            results.append(
                {
                    "title": item["filename"],
                    "indexer": "Zilean",
                    "guid": item["infoHash"],
                    "infoHash": item["infoHash"],
                    "size": item["filesize"],
                    "qualityTitle": "",
                    "seeders": 0,
                    "languages": "",
                    "fullLanguages": "",
                    "publishDate": "",
                    "peers": 0,
                }
            )
        return results

    def ping(self, additional_headers=None):
        return self.session.get(
            f"{self.url}/healthchecks/ping",
            headers=additional_headers,
            timeout=self.timeout,
        )


class RateLimitExceeded(Exception):
    pass
