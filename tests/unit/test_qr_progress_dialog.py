from unittest.mock import MagicMock

from lib.gui.qr_progress_dialog import QRProgressDialog


def test_on_action_marks_dialog_canceled_before_closing():
    dialog = QRProgressDialog("qr_dialog.xml", "")
    dialog.close_dialog = MagicMock()

    action = MagicMock()
    action.getId.return_value = 92

    dialog.onAction(action)

    assert dialog.iscanceled is True
    dialog.close_dialog.assert_called_once_with()


def test_on_action_ignores_non_close_actions():
    dialog = QRProgressDialog("qr_dialog.xml", "")
    dialog.close_dialog = MagicMock()

    action = MagicMock()
    action.getId.return_value = 7

    dialog.onAction(action)

    assert dialog.iscanceled is False
    dialog.close_dialog.assert_not_called()
