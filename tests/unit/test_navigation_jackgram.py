from unittest.mock import call, patch

from lib import navigation, router


def test_search_jackgram_delegates_to_isolated_history_without_direct_search():
    with patch.object(
        navigation.library_history_navigation, "search_direct", return_value="result"
    ) as search_direct, patch("lib.search.run_search_entry") as run_search_entry:
        result = navigation.search_jackgram({"jackgram_only": "false", "history_key": "direct"})

    assert result == "result"
    search_direct.assert_called_once_with(
        {
            "jackgram_only": "true",
            "history_key": "direct_jackgram",
            "mode": "direct",
            "label_id": 30262,
        }
    )
    run_search_entry.assert_not_called()


def test_telegram_menu_includes_jackgram_actions_without_global_search():
    with patch.object(navigation, "set_pluging_category"), patch.object(
        navigation, "build_url", side_effect=lambda action, **kwargs: (action, kwargs)
    ) as build_url, patch.object(navigation, "build_list_item"), patch.object(
        navigation, "addDirectoryItem"
    ), patch.object(navigation, "end_of_directory"), patch.object(
        navigation, "apply_section_view"
    ), patch.object(navigation, "translation") as translation:
        navigation.telegram_menu({})

    assert call("search_jackgram", mode="direct") in build_url.call_args_list
    assert call("search_direct", mode="direct") not in build_url.call_args_list
    assert call("list_jackgram_latest_movies", page=1) in build_url.call_args_list
    assert call("list_jackgram_latest_series", page=1) in build_url.call_args_list
    assert call("list_jackgram_raw_files", page=1) in build_url.call_args_list
    assert call("test_jackgram_connection") in build_url.call_args_list
    translation.assert_any_call(30262)


def test_router_routes_search_jackgram_to_navigation():
    params = {"query": "Dune"}
    with patch("lib.navigation.search_jackgram") as search_jackgram:
        router._route_telegram("search_jackgram", params)

    assert router._is_telegram_action("search_jackgram") is True
    search_jackgram.assert_called_once_with(params)
