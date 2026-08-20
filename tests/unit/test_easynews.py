from unittest.mock import MagicMock

from lib.clients.easynews import Easynews


def test_parse_response_adds_https_to_protocol_relative_download_url():
    response = MagicMock()
    response.json.return_value = {
        "downURL": "//members.easynews.com",
        "dlFarm": "farm1",
        "dlPort": "443",
        "data": [
            {
                "0": "posthash",
                "4": "1024",
                "10": "Example 1080p",
                "11": ".mkv",
                "14": "1h",
                "type": "VIDEO",
            }
        ],
    }

    results = Easynews("user", "password", 10, MagicMock()).parse_response(response)

    assert results[0].url == "https://members.easynews.com/farm1/443/posthash.mkv/Example%201080p.mkv"
