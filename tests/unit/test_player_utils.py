from unittest.mock import patch
from urllib.parse import quote


def test_elementum_prefers_url_when_url_and_magnet_exist():
    from lib.utils.player import utils

    magnet = "magnet:?xt=urn:btih:PRIVATEHASH"
    url = "https://jackett.example/dl/private-tracker?id=123&apikey=token"

    with patch.object(utils, "is_elementum_addon", return_value=True):
        elementum_url = utils.get_elementum_url(
            magnet,
            url,
            "movie",
            {"tmdb_id": "100"},
        )

    assert f"uri={quote(url)}" in elementum_url
    assert quote(magnet) not in elementum_url


def test_elementum_client_prefers_url_when_url_and_magnet_exist():
    from lib.utils.general.utils import Players
    from lib.utils.player import utils

    magnet = "magnet:?xt=urn:btih:PRIVATEHASH"
    url = "https://jackett.example/dl/private-tracker?id=123&apikey=token"

    with patch.object(utils, "is_elementum_addon", return_value=True):
        elementum_url = utils.get_torrent_url_for_client(
            magnet,
            url,
            "movie",
            {"tmdb_id": "100"},
            client=Players.ELEMENTUM,
        )

    assert f"uri={quote(url)}" in elementum_url
    assert quote(magnet) not in elementum_url


def test_elementum_uses_magnet_when_only_magnet_exists():
    from lib.utils.player import utils

    magnet = "magnet:?xt=urn:btih:ONLYMAGNET"

    with patch.object(utils, "is_elementum_addon", return_value=True):
        magnet_url = utils.get_elementum_url(magnet, "", "movie", {"tmdb_id": "100"})

    assert f"uri={quote(magnet)}" in magnet_url


def test_elementum_uses_url_when_only_url_exists():
    from lib.utils.player import utils

    url = "https://example.com/only-url.torrent"

    with patch.object(utils, "is_elementum_addon", return_value=True):
        torrent_url = utils.get_elementum_url("", url, "movie", {"tmdb_id": "100"})

    assert f"uri={quote(url)}" in torrent_url


def test_jacktorr_playback_saves_metadata_under_infohash_and_magnet_hash():
    from lib.utils.player import utils

    data = {
        "title": "FROM",
        "mode": "tv",
        "ids": {"imdb_id": "tt9813792"},
        "tv_data": {"season": 4, "episode": 2, "name": "Fray"},
        "info_hash": "SOURCEHASH",
    }

    with patch.object(utils, "is_jacktorr_addon", return_value=True), patch(
        "lib.utils.general.utils.get_info_hash_from_magnet", return_value="MAGNETHASH"
    ), patch("lib.utils.torrent.torrserver_utils.save_torrent_meta") as mock_save:
        url = utils.get_jacktorr_url("magnet:?xt=urn:btih:MAGNETHASH", "", data=data)

    assert url.startswith("plugin://plugin.video.jacktorr/play_magnet")
    saved_hashes = [call.args[0] for call in mock_save.call_args_list]
    assert saved_hashes == ["SOURCEHASH", "MAGNETHASH"]
    assert all(call.args[1]["ids"]["imdb_id"] == "tt9813792" for call in mock_save.call_args_list)
    assert all(call.args[1]["mode"] == "tv" for call in mock_save.call_args_list)


def test_jacktorr_playback_deduplicates_matching_infohash_and_magnet_hash():
    from lib.utils.player import utils

    data = {
        "title": "FROM",
        "mode": "tv",
        "ids": {"imdb_id": "tt9813792"},
        "tv_data": {"season": 4, "episode": 2},
        "info_hash": "SAMEHASH",
    }

    with patch.object(utils, "is_jacktorr_addon", return_value=True), patch(
        "lib.utils.general.utils.get_info_hash_from_magnet", return_value="SAMEHASH"
    ), patch("lib.utils.torrent.torrserver_utils.save_torrent_meta") as mock_save:
        utils.get_jacktorr_url("magnet:?xt=urn:btih:SAMEHASH", "", data=data)

    mock_save.assert_called_once()
    assert mock_save.call_args.args[0] == "SAMEHASH"
