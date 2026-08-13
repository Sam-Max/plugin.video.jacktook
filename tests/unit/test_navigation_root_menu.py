from unittest.mock import patch

from lib import navigation


def test_root_menu_reuses_condition_results_for_entries_and_cache():
    calls = {"continue_watching": 0, "simkl": 0, "trakt": 0, "telegram": 0}
    rendered_entries = []

    def continue_watching_condition():
        calls["continue_watching"] += 1
        return True

    def simkl_condition():
        calls["simkl"] += 1
        return calls["simkl"] > 1

    def trakt_condition():
        calls["trakt"] += 1
        return False

    def telegram_condition():
        calls["telegram"] += 1
        return False

    items = [
        {"name": 100, "icon": "base.png", "action": "base"},
        {
            "name": "First",
            "icon": "first.png",
            "action": "first",
            "condition": continue_watching_condition,
        },
        {
            "name": "Second",
            "icon": "second.png",
            "action": "second",
            "condition": simkl_condition,
        },
        {
            "name": "Trakt",
            "icon": "trakt.png",
            "action": "trakt",
            "condition": trakt_condition,
        },
        {
            "name": "Telegram",
            "icon": "telegram.png",
            "action": "telegram",
            "condition": telegram_condition,
        },
    ]

    navigation.RuntimeCache.clear()
    with patch.object(navigation, "root_menu_items", items), patch.object(
        navigation, "maybe_show_donation_prompt"
    ), patch.object(navigation, "set_pluging_category"), patch.object(
        navigation, "apply_section_view"
    ), patch.object(
        navigation, "translation", side_effect=lambda value: f"label-{value}"
    ), patch.object(
        navigation, "build_url", side_effect=lambda action, **_kwargs: action
    ) as build_url, patch.object(
        navigation, "_render_cached_menu_entries", side_effect=rendered_entries.append
    ), patch.object(navigation, "end_of_directory"):
        navigation.root_menu()
        navigation.root_menu()
        navigation.root_menu()

    assert calls == {"continue_watching": 3, "simkl": 3, "trakt": 3, "telegram": 3}
    assert rendered_entries == [
        [
            {"name": "label-100", "icon": "base.png", "url": "base", "is_folder": True},
            {"name": "First", "icon": "first.png", "url": "first", "is_folder": True},
        ],
        [
            {"name": "label-100", "icon": "base.png", "url": "base", "is_folder": True},
            {"name": "First", "icon": "first.png", "url": "first", "is_folder": True},
            {"name": "Second", "icon": "second.png", "url": "second", "is_folder": True},
        ],
        [
            {"name": "label-100", "icon": "base.png", "url": "base", "is_folder": True},
            {"name": "First", "icon": "first.png", "url": "first", "is_folder": True},
            {"name": "Second", "icon": "second.png", "url": "second", "is_folder": True},
        ],
    ]
    assert build_url.call_count == 5
