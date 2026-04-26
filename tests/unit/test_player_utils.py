from unittest.mock import patch


def test_jacktorr_playback_saves_metadata_under_infohash_and_magnet_hash():
    from lib.utils.player import utils

    data = {
        "title": "FROM",
        "mode": "tv",
        "ids": {"imdb_id": "tt9813792"},
        "tv_data": {"season": 4, "episode": 2, "name": "Fray"},
        "info_hash": "SOURCEHASH",
    }

    with patch.object(utils, "is_jacktorr_addon", return_value=True), \
         patch("lib.utils.general.utils.get_info_hash_from_magnet", return_value="MAGNETHASH"), \
         patch("lib.utils.torrent.torrserver_utils.save_torrent_meta") as mock_save:
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

    with patch.object(utils, "is_jacktorr_addon", return_value=True), \
         patch("lib.utils.general.utils.get_info_hash_from_magnet", return_value="SAMEHASH"), \
         patch("lib.utils.torrent.torrserver_utils.save_torrent_meta") as mock_save:
        utils.get_jacktorr_url("magnet:?xt=urn:btih:SAMEHASH", "", data=data)

    mock_save.assert_called_once()
    assert mock_save.call_args.args[0] == "SAMEHASH"
