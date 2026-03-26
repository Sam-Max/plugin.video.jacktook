from unittest.mock import MagicMock, patch

from lib.services.debrid.auth import run_alldebrid_auth


@patch(
    "lib.services.debrid.auth.translation",
    side_effect=lambda value: "%s" if value == 90604 else str(value),
)
@patch("lib.services.debrid.auth.set_setting")
@patch("lib.services.debrid.auth.copy2clip")
@patch("lib.services.debrid.auth.make_qrcode", return_value="/tmp/qr.png")
@patch("lib.services.debrid.auth.ksleep")
@patch("lib.services.debrid.auth.time", side_effect=[0, 1])
@patch("lib.services.debrid.auth.QRProgressDialog")
def test_run_alldebrid_auth_reauths_even_with_existing_token(
    mock_dialog_cls,
    mock_time,
    mock_sleep,
    mock_make_qrcode,
    mock_copy2clip,
    mock_set_setting,
    mock_translation,
):
    client = MagicMock()
    client.token = "stale-token"
    client.get_ping.return_value = {
        "data": {
            "expires_in": 600,
            "pin": "ABCD",
            "check": "check-id",
            "user_url": "https://alldebrid.com/pin/?pin=ABCD",
        }
    }
    client.poll_auth.return_value = {"activated": True, "apikey": "fresh-token"}
    client.get_user_info.return_value = {"user": {"username": "tester"}}

    dialog = MagicMock()
    dialog.iscanceled = False
    mock_dialog_cls.return_value = dialog

    run_alldebrid_auth(client)

    client.initialize_headers.assert_called()
    client.poll_auth.assert_called_once_with("check-id", "ABCD")
    assert client.token == "fresh-token"
    dialog.show_dialog.assert_called_once_with()
    dialog.update_progress.assert_called_with(100, "90545")
    dialog.close_dialog.assert_called_once_with()
    mock_set_setting.assert_any_call("alldebrid_token", "fresh-token")
    mock_set_setting.assert_any_call("alldebrid_authorized", "true")
    mock_set_setting.assert_any_call("alldebrid_user", "tester")
