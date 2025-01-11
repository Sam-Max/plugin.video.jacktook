import requests
from urllib.parse import urlparse, urlunparse

def normalize_transmission_url(url):
    parsed_url = urlparse(url)
    
    if not parsed_url.scheme:
        url = f"http://{url}"
        parsed_url = urlparse(url)
    
    netloc = parsed_url.netloc
    if ":" not in netloc:
        netloc = f"{netloc}:9091"
    
    path = parsed_url.path
    if not path or path == "/":
        path = "/transmission/rpc"

    normalized_url = urlunparse((parsed_url.scheme, netloc, path, "", "", ""))
    return normalized_url

def queue_torrent_to_transmission(infohash, transmission_url="http://localhost:9091", username=None, password=None):
    transmission_url = normalize_transmission_url(transmission_url)
    magnet_link = f"magnet:?xt=urn:btih:{infohash}"
    
    session = requests.Session()
    
    if username and password:
        session.auth = (username, password)
    
    # Fetch the CSRF token by making an initial request
    response = session.get(transmission_url)

    csrf_token = response.headers.get("x-transmission-session-id")
    if not csrf_token:
        raise Exception("Could not retrieve CSRF token from Transmission.")
    
    payload = {
        "method": "torrent-add",
        "arguments": {
            "filename": magnet_link,
            "paused": False
        }
    }
    
    headers = {
        "x-transmission-session-id": csrf_token
    }
    
    response = session.post(transmission_url, json=payload, headers=headers)
    
      
    if response.status_code != 200:
        raise Exception(f"Failed to add torrent. Status code: {response.status_code}, Response: {response.text}")
    
    return response.json()