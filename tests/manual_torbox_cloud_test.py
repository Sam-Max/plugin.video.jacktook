import json
from pathlib import Path
import xml.etree.ElementTree as ET

import requests


SETTINGS_PATHS = [
    Path("/home/spider/.kodi/userdata/addon_data/plugin.video.jacktook/settings.xml"),
    Path("/home/spider/.var/app/tv.kodi.Kodi/data/userdata/addon_data/plugin.video.jacktook/settings.xml"),
]
BASE_URL = "https://api.torbox.app/v1/api"
VIDEO_EXTENSIONS = (".mp4", ".mkv", ".avi", ".ts", ".m2ts")
MAX_LINK_TESTS = 20


def load_saved_torbox_settings():
    for path in SETTINGS_PATHS:
        if not path.exists():
            continue

        root = ET.parse(path).getroot()
        settings = {
            element.get("id"): (element.text or element.get("value") or "")
            for element in root.findall(".//setting")
        }
        token = settings.get("torbox_token", "")
        enabled = settings.get("torbox_enabled", "")
        if token:
            return {
                "path": str(path),
                "enabled": enabled,
                "token": token,
            }

    raise RuntimeError("No saved Torbox token found in known addon settings files")


def api_get(token, endpoint, params=None):
    headers = {
        "User-Agent": "Jacktook/1.0",
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
    }
    response = requests.get(
        f"{BASE_URL}{endpoint}", headers=headers, params=params, timeout=20
    )
    response.raise_for_status()
    return response.json()


def pick_playable_file(files):
    playable_files = []
    for file_item in files or []:
        name = str(file_item.get("name") or file_item.get("short_name") or "")
        if name.lower().endswith(VIDEO_EXTENSIONS):
            playable_files.append(file_item)

    if not playable_files:
        return None

    return max(playable_files, key=lambda item: item.get("size", 0))


def main():
    saved = load_saved_torbox_settings()
    token = saved["token"]

    print("=== Torbox Cloud Manual Test ===")
    print(f"Settings file: {saved['path']}")
    print(f"Torbox enabled: {saved['enabled']}")
    print(f"Token present: {bool(token)} (length={len(token)})")

    me = api_get(token, "/user/me")
    print(f"/user/me success: {me.get('success')}")

    listing = api_get(token, "/torrents/mylist", params={"bypass_cache": "true"})
    torrents = listing.get("data") or []
    print(f"/torrents/mylist success: {listing.get('success')}")
    print(f"Torrent count: {len(torrents)}")

    downloadable = []
    candidate_count = 0
    skipped = {
        "not_dict": 0,
        "download_not_present": 0,
        "no_playable_files": 0,
        "link_failed": 0,
    }

    for torrent in torrents:
        if not isinstance(torrent, dict):
            skipped["not_dict"] += 1
            continue

        if not torrent.get("download_present"):
            skipped["download_not_present"] += 1
            continue

        file_item = pick_playable_file(torrent.get("files") or [])
        if not file_item:
            skipped["no_playable_files"] += 1
            continue

        candidate_count += 1
        if candidate_count > MAX_LINK_TESTS:
            continue

        link = api_get(
            token,
            "/torrents/requestdl",
            params={
                "token": token,
                "torrent_id": torrent.get("id"),
                "file_id": file_item.get("id"),
            },
        )
        if not link.get("success") or not link.get("data"):
            skipped["link_failed"] += 1
            continue

        downloadable.append(
            {
                "torrent": torrent.get("name"),
                "file": file_item.get("name"),
                "download": link.get("data"),
            }
        )

    print("Skips:", json.dumps(skipped, indent=2))
    print(f"Playable download candidates: {candidate_count}")
    print(f"Link tests executed: {min(candidate_count, MAX_LINK_TESTS)}")
    print(f"Downloadable entries found: {len(downloadable)}")

    for index, item in enumerate(downloadable[:5], start=1):
        print(f"\n[{index}] Torrent: {item['torrent']}")
        print(f"    File: {item['file']}")
        print(f"    URL: {item['download'][:140]}...")


if __name__ == "__main__":
    main()
