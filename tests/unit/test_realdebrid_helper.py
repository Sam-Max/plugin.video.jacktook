from unittest.mock import MagicMock

from lib.clients.debrid.realdebrid import RealDebridHelper


def test_get_link_multi_file_movie_uses_largest_selected_file():
    helper = RealDebridHelper.__new__(RealDebridHelper)
    helper.client = MagicMock()
    helper.add_magnet = MagicMock(return_value="torrent-id")

    helper.client.get_torrent_info.return_value = {
        "links": ["link-small", "link-large", "link-medium"],
        "files": [
            {"selected": 1, "bytes": 100},
            {"selected": 1, "bytes": 300},
            {"selected": 1, "bytes": 200},
        ],
    }
    helper.client.create_download_link.side_effect = lambda link: {
        "download": "https://download/{}".format(link)
    }

    result = helper.get_link("info-hash", {})

    assert result["url"] == "https://download/link-large"
    assert "is_pack" not in result


def test_get_link_multi_file_movie_falls_back_to_pack_when_no_selected_files():
    helper = RealDebridHelper.__new__(RealDebridHelper)
    helper.client = MagicMock()
    helper.add_magnet = MagicMock(return_value="torrent-id")

    helper.client.get_torrent_info.return_value = {
        "links": ["link-one", "link-two"],
        "files": [{"selected": 0, "bytes": 100}, {"selected": 0, "bytes": 200}],
    }

    result = helper.get_link("info-hash", {})

    assert result["is_pack"] is True
    assert "url" not in result
