import hashlib
import requests
from lib.bencodepy import bencodepy
from lib.utils.kodi import log


def extract_magnet_from_url(url: str) -> dict:
    try:
        response = requests.get(url)
        if response.status_code == 200:
            content = response.content
            return extract_torrent_metadata(content)
        else:
            log.error(f"Failed to fetch content from URL: {url}")
            return {}
    except Exception as e:
        log.error(f"Error occurred: {e}")
        return {}


def extract_torrent_metadata(content: bytes) -> dict:
    try:
        torrent_data = bencodepy.decode(content)
        info = torrent_data[b"info"]
        info_encoded = bencodepy.encode(info)
        m = hashlib.sha1()
        m.update(info_encoded)
        info_hash = m.hexdigest()
        return convert_info_hash_to_magnet(info_hash)
    except Exception as e:
        log.error(f"Error occurred: {e}")
        return {}


def convert_info_hash_to_magnet(info_hash: str) -> str:
    magnet_link = f"magnet:?xt=urn:btih:{info_hash}"
    return magnet_link
