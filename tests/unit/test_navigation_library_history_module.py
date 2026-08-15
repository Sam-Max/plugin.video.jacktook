from unittest.mock import MagicMock, patch

from lib.nav import library_history


def test_history_menu_renders_history_items():
    with patch("lib.nav.library_history.set_pluging_category") as set_category, patch(
        "lib.nav.library_history.add_directory_items_batch"
    ) as add_directory_items_batch, patch("lib.nav.library_history.end_of_directory"), patch(
        "lib.nav.library_history.build_url", side_effect=lambda action, **kwargs: action
    ), patch(
        "lib.nav.library_history.build_list_item",
        side_effect=lambda label, *_args, **_kwargs: label,
    ):
        library_history.history_menu({})

    set_category.assert_called_once()
    assert add_directory_items_batch.called


def test_clear_history_delegates_and_notifies():
    with patch("lib.nav.library_history.clear_history_by_type") as clear_history, patch(
        "lib.nav.library_history.notification"
    ) as notify, patch("lib.nav.library_history.translation", return_value="done"):
        library_history.clear_history({"type": "movies"})

    clear_history.assert_called_once_with(type="movies")
    notify.assert_called_once_with("done")


def test_direct_search_history_context_menu_opens_source_manager():
    search_item = MagicMock()
    history_item = MagicMock()
    clear_item = MagicMock()

    with patch("lib.nav.library_history.cache.get_list", return_value=[("direct", "Demo")]), patch(
        "lib.nav.library_history.make_list_item",
        side_effect=[search_item, history_item, clear_item],
    ), patch("lib.nav.library_history.set_pluging_category"), patch(
        "lib.nav.library_history.show_keyboard", return_value=""
    ), patch("lib.nav.library_history.addDirectoryItem"), patch(
        "lib.nav.library_history.endOfDirectory"
    ), patch("lib.nav.library_history.apply_section_view"), patch(
        "lib.nav.library_history.translation", side_effect=lambda value: f"t-{value}"
    ):
        library_history.search_direct({"mode": "direct"})

    context_menu = history_item.addContextMenuItems.call_args.args[0]
    assert (
        "t-90755",
        "RunPlugin(plugin://plugin.video.jacktook/?action=source_manager_toggle)",
    ) in context_menu


def test_jackgram_search_history_uses_isolated_cache_and_filtered_links():
    search_item = MagicMock()
    history_item = MagicMock()
    clear_item = MagicMock()

    with patch("lib.nav.library_history.cache.add_to_list") as add_to_list, patch(
        "lib.nav.library_history.cache.get_list", return_value=[("direct", "Dune")]
    ) as get_list, patch(
        "lib.nav.library_history.make_list_item",
        side_effect=[search_item, history_item, clear_item],
    ) as make_list_item, patch("lib.nav.library_history.set_pluging_category"), patch(
        "lib.nav.library_history.show_keyboard", return_value="Dune"
    ), patch("lib.nav.library_history.addDirectoryItem"), patch(
        "lib.nav.library_history.endOfDirectory"
    ), patch("lib.nav.library_history.apply_section_view"), patch(
        "lib.nav.library_history.translation", side_effect=lambda value: f"t-{value}"
    ), patch("lib.nav.library_history.build_url") as build_url, patch(
        "lib.nav.library_history.kodi_play_media"
    ) as kodi_play_media, patch("lib.nav.library_history.container_update") as container_update:
        library_history.search_direct(
            {
                "mode": "direct",
                "history_key": "direct_jackgram",
                "jackgram_only": "true",
                "label_id": 30262,
            }
        )

    add_to_list.assert_called_once()
    assert add_to_list.call_args.kwargs["key"] == "direct_jackgram"
    assert add_to_list.call_args.kwargs["item"] == ("direct", "Dune")
    get_list.assert_called_once_with(key="direct_jackgram")
    assert make_list_item.call_args_list[0].kwargs["label"] == "t-30262"
    assert any(
        url_call[0][0] == "search"
        and url_call[1]["jackgram_only"] == "true"
        and url_call[1]["history_key"] == "direct_jackgram"
        for url_call in build_url.call_args_list
    )
    assert kodi_play_media.call_args.kwargs["jackgram_only"] == "true"
    assert kodi_play_media.call_args.kwargs["history_key"] == "direct_jackgram"
    assert container_update.call_args.kwargs["jackgram_only"] == "true"
    assert container_update.call_args.kwargs["history_key"] == "direct_jackgram"
    clear_call = next(
        url_call for url_call in build_url.call_args_list if url_call[1].get("is_clear")
    )
    assert clear_call[1]["jackgram_only"] == "true"
    assert clear_call[1]["history_key"] == "direct_jackgram"


def test_global_search_history_keeps_direct_key_without_jackgram_filter():
    with patch("lib.nav.library_history.cache.add_to_list") as add_to_list, patch(
        "lib.nav.library_history.cache.get_list", return_value=[]
    ), patch("lib.nav.library_history.make_list_item", return_value=MagicMock()), patch(
        "lib.nav.library_history.set_pluging_category"
    ), patch("lib.nav.library_history.show_keyboard", return_value="Dune"), patch(
        "lib.nav.library_history.addDirectoryItem"
    ), patch("lib.nav.library_history.endOfDirectory"), patch(
        "lib.nav.library_history.apply_section_view"
    ), patch("lib.nav.library_history.build_url") as build_url:
        library_history.search_direct({"mode": "direct"})

    assert add_to_list.call_args.kwargs["key"] == "direct"
    assert all("jackgram_only" not in url_call[1] for url_call in build_url.call_args_list)


def test_cancelled_jackgram_search_history_does_not_write_cache():
    with patch("lib.nav.library_history.cache.add_to_list") as add_to_list, patch(
        "lib.nav.library_history.cache.get_list", return_value=[]
    ), patch("lib.nav.library_history.make_list_item", return_value=MagicMock()), patch(
        "lib.nav.library_history.set_pluging_category"
    ), patch("lib.nav.library_history.show_keyboard", return_value=""), patch(
        "lib.nav.library_history.addDirectoryItem"
    ), patch("lib.nav.library_history.endOfDirectory") as end_of_directory, patch(
        "lib.nav.library_history.apply_section_view"
    ):
        library_history.search_direct(
            {
                "mode": "direct",
                "history_key": "direct_jackgram",
                "jackgram_only": "true",
            }
        )

    add_to_list.assert_not_called()
    end_of_directory.assert_called_once()
