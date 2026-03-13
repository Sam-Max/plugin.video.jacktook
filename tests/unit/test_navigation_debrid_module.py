from unittest.mock import patch

from lib.nav import debrid as debrid_navigation


def test_cloud_details_uses_registry_actions_for_realdebrid():
    with patch("lib.nav.debrid.addDirectoryItem") as add_directory_item, patch(
        "lib.nav.debrid.end_of_directory"
    ), patch(
        "lib.nav.debrid.build_url", side_effect=lambda action, **kwargs: action
    ), patch(
        "lib.nav.debrid.build_list_item", side_effect=lambda label, *_args, **_kwargs: label
    ):
        debrid_navigation.cloud_details({"debrid_name": debrid_navigation.DebridType.RD})

    assert add_directory_item.call_args_list[0].args[1] == "get_rd_downloads"
    assert add_directory_item.call_args_list[1].args[1] == "real_debrid_info"


def test_download_notifies_on_unknown_debrid_type():
    with patch("lib.nav.debrid.notification") as notify:
        debrid_navigation.download("magnet:?xt=urn:btih:123", "UNKNOWN")

    notify.assert_called_once_with("Unsupported debrid type")
