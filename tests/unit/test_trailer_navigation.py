from unittest.mock import MagicMock, patch


def test_play_trailer_resolves_and_hands_off_to_kodi():
    params = {
        "yt_id": "dQw4w9WgXcQ",
        "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "tmdb_id": "550",
        "media_type": "movie",
        "title": "Demo Movie",
    }
    list_item = MagicMock()

    with patch(
        "lib.navigation.resolve_item_trailer",
        return_value={
            "trailer": {"yt_id": "dQw4w9WgXcQ", "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
            "playback": {"video_url": "https://video.example/trailer.m3u8", "source_type": "hls"},
        },
    ) as resolve_item_trailer, patch("lib.navigation.ListItem", return_value=list_item) as list_item_cls, patch(
        "lib.navigation.setResolvedUrl"
    ) as set_resolved_url, patch("lib.navigation.notification") as notification:
        from lib.navigation import play_trailer

        play_trailer(params)

    resolve_item_trailer.assert_called_once_with(
        yt_id="dQw4w9WgXcQ",
        youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        tmdb_id="550",
        media_type="movie",
    )
    list_item_cls.assert_called_once_with(
        label="Demo Movie",
        path="https://video.example/trailer.m3u8",
    )
    list_item.setPath.assert_called_once_with("https://video.example/trailer.m3u8")
    list_item.setProperty.assert_called_once_with("IsPlayable", "true")
    set_resolved_url.assert_called_once_with(1, True, list_item)
    notification.assert_not_called()


def test_play_trailer_handles_adaptive_source_without_falling_back_to_youtube_addon():
    list_item = MagicMock()

    with patch(
        "lib.navigation.resolve_item_trailer",
        return_value={
            "trailer": {"yt_id": "dQw4w9WgXcQ"},
            "playback": {
                "video_url": "https://video.example/video-1080.mp4",
                "audio_url": "https://video.example/audio-160.m4a",
                "source_type": "adaptive",
            },
        },
    ), patch("lib.navigation.ListItem", return_value=list_item) as list_item_cls, patch(
        "lib.navigation.setResolvedUrl"
    ) as set_resolved_url, patch("lib.navigation.execute_builtin") as execute_builtin:
        from lib.navigation import play_trailer

        play_trailer({"tmdb_id": "550", "media_type": "movie", "title": "Demo Movie"})

    list_item_cls.assert_called_once_with(
        label="Demo Movie",
        path="https://video.example/video-1080.mp4",
    )
    list_item.setPath.assert_called_once_with("https://video.example/video-1080.mp4")
    assert list_item.setProperty.call_args_list == [
        (("IsPlayable", "true"),),
        (("inputstream.adaptive.manifest_type", "mpd"),),
    ]
    set_resolved_url.assert_called_once_with(1, True, list_item)
    execute_builtin.assert_not_called()


def test_play_trailer_notifies_when_no_resolved_video_url():
    with patch(
        "lib.navigation.resolve_item_trailer",
        return_value=None,
    ) as resolve_item_trailer, patch(
        "lib.navigation.translation",
        side_effect=lambda value: "Trailer unavailable" if value == 90673 else f"t-{value}",
    ), patch("lib.navigation.notification") as notification, patch(
        "lib.navigation.setResolvedUrl"
    ) as set_resolved_url:
        from lib.navigation import play_trailer

        play_trailer({"tmdb_id": "1399", "media_type": "tv", "title": "Demo Show"})

    resolve_item_trailer.assert_called_once_with(
        yt_id=None,
        youtube_url=None,
        tmdb_id="1399",
        media_type="tv",
    )
    notification.assert_called_once_with("Trailer unavailable")
    set_resolved_url.assert_not_called()


def test_play_trailer_uses_mode_when_media_type_missing():
    with patch(
        "lib.navigation.resolve_item_trailer",
        return_value={"trailer": {"yt_id": None}, "playback": {"audio_url": "https://video.example/audio.m4a"}},
    ) as resolve_item_trailer, patch("lib.navigation.translation", side_effect=lambda value: "Trailer unavailable" if value == 90673 else f"t-{value}"), patch("lib.navigation.notification") as notification:
        from lib.navigation import play_trailer

        play_trailer({"tmdb_id": "1399", "mode": "tv", "title": "Demo Show"})

    resolve_item_trailer.assert_called_once_with(
        yt_id=None,
        youtube_url=None,
        tmdb_id="1399",
        media_type="tv",
    )
    notification.assert_called_once_with("Trailer unavailable")


def test_play_trailer_logs_when_resolution_fails():
    with patch(
        "lib.navigation.resolve_item_trailer",
        return_value=None,
    ), patch("lib.navigation.kodilog") as log_mock, patch(
        "lib.navigation.translation",
        side_effect=lambda value: "Trailer unavailable" if value == 90673 else f"t-{value}",
    ), patch(
        "lib.navigation.notification"
    ):
        from lib.navigation import play_trailer

        play_trailer({"tmdb_id": "1399", "media_type": "tv", "title": "Demo Show"})

    log_mock.assert_called()


def test_play_trailer_falls_back_to_youtube_addon_when_direct_playback_unavailable():
    with patch(
        "lib.navigation.resolve_item_trailer",
        return_value={"trailer": {"yt_id": "dQw4w9WgXcQ"}, "playback": None},
    ) as resolve_item_trailer, patch(
        "lib.navigation.is_youtube_addon_enabled",
        return_value=True,
    ) as is_youtube_addon_enabled, patch(
        "lib.navigation.execute_builtin"
    ) as execute_builtin, patch("lib.navigation.notification") as notification, patch(
        "lib.navigation.setResolvedUrl"
    ) as set_resolved_url:
        from lib.navigation import play_trailer

        play_trailer(
            {
                "tmdb_id": "550",
                "media_type": "movie",
                "title": "Demo Movie",
                "yt_id": "dQw4w9WgXcQ",
            }
        )

    resolve_item_trailer.assert_called_once_with(
        yt_id="dQw4w9WgXcQ",
        youtube_url=None,
        tmdb_id="550",
        media_type="movie",
    )
    is_youtube_addon_enabled.assert_called_once_with()
    execute_builtin.assert_called_once_with(
        "PlayMedia(plugin://plugin.video.youtube/play/?video_id=dQw4w9WgXcQ)"
    )
    notification.assert_not_called()
    set_resolved_url.assert_not_called()


def test_play_trailer_notifies_when_direct_playback_unavailable_and_no_youtube_id():
    with patch(
        "lib.navigation.resolve_item_trailer",
        return_value=None,
    ) as resolve_item_trailer, patch(
        "lib.navigation.is_youtube_addon_enabled",
        return_value=True,
    ) as is_youtube_addon_enabled, patch("lib.navigation.translation", side_effect=lambda value: "Trailer unavailable" if value == 90673 else f"t-{value}"), patch(
        "lib.navigation.execute_builtin"
    ) as execute_builtin, patch("lib.navigation.notification") as notification:
        from lib.navigation import play_trailer

        play_trailer(
            {
                "tmdb_id": "550",
                "media_type": "movie",
                "title": "Demo Movie",
            }
        )

    resolve_item_trailer.assert_called_once_with(
        yt_id=None,
        youtube_url=None,
        tmdb_id="550",
        media_type="movie",
    )
    is_youtube_addon_enabled.assert_not_called()
    execute_builtin.assert_not_called()
    notification.assert_called_once_with("Trailer unavailable")


def test_play_trailer_falls_back_to_tmdb_derived_youtube_addon_playback():
    with patch(
        "lib.navigation.resolve_item_trailer",
        return_value={
            "trailer": {
                "yt_id": "tmdb1234567",
                "youtube_url": "https://www.youtube.com/watch?v=tmdb1234567",
            },
            "playback": None,
        },
    ) as resolve_item_trailer, patch(
        "lib.navigation.is_youtube_addon_enabled",
        return_value=True,
    ) as is_youtube_addon_enabled, patch(
        "lib.navigation.execute_builtin"
    ) as execute_builtin, patch("lib.navigation.notification") as notification:
        from lib.navigation import play_trailer

        play_trailer(
            {
                "tmdb_id": "550",
                "media_type": "movie",
                "title": "Demo Movie",
            }
        )

    resolve_item_trailer.assert_called_once_with(
        yt_id=None,
        youtube_url=None,
        tmdb_id="550",
        media_type="movie",
    )
    is_youtube_addon_enabled.assert_called_once_with()
    execute_builtin.assert_called_once_with(
        "PlayMedia(plugin://plugin.video.youtube/play/?video_id=tmdb1234567)"
    )
    notification.assert_not_called()


def test_play_trailer_notifies_when_youtube_addon_is_missing_for_fallback():
    with patch(
        "lib.navigation.resolve_item_trailer",
        return_value={
            "trailer": {"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
            "playback": None,
        },
    ) as resolve_item_trailer, patch(
        "lib.navigation.is_youtube_addon_enabled",
        return_value=False,
    ) as is_youtube_addon_enabled, patch("lib.navigation.translation", side_effect=lambda value: "Trailer unavailable" if value == 90673 else f"t-{value}"), patch(
        "lib.navigation.execute_builtin"
    ) as execute_builtin, patch("lib.navigation.notification") as notification:
        from lib.navigation import play_trailer

        play_trailer(
            {
                "tmdb_id": "550",
                "media_type": "movie",
                "title": "Demo Movie",
                "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            }
        )

    resolve_item_trailer.assert_called_once_with(
        yt_id=None,
        youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        tmdb_id="550",
        media_type="movie",
    )
    is_youtube_addon_enabled.assert_called_once_with()
    execute_builtin.assert_not_called()
    notification.assert_called_once_with("Trailer unavailable")


def test_play_trailer_logs_unavailable_youtube_addon_fallback_details():
    with patch(
        "lib.navigation.resolve_item_trailer",
        return_value={
            "trailer": {
                "yt_id": "tmdb1234567",
                "youtube_url": "https://www.youtube.com/watch?v=tmdb1234567",
            },
            "playback": None,
        },
    ), patch(
        "lib.navigation.is_youtube_addon_enabled",
        return_value=False,
    ), patch(
        "lib.navigation.translation",
        side_effect=lambda value: "Trailer unavailable" if value == 90673 else f"t-{value}",
    ), patch(
        "lib.navigation.notification"
    ), patch("lib.navigation.kodilog") as log_mock:
        from lib.navigation import play_trailer

        play_trailer(
            {
                "tmdb_id": "550",
                "media_type": "movie",
                "title": "Demo Movie",
            }
        )

    logged_messages = [call.args[0] for call in log_mock.call_args_list]
    assert (
        "Trailer: youtube addon unavailable title='Demo Movie' media_type='movie' tmdb_id='550' fallback_yt_id='tmdb1234567'"
        in logged_messages
    )
