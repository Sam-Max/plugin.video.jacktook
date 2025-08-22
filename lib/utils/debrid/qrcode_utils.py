from os import path

from lib.jacktook.utils import ADDON_PATH, kodilog
from lib.utils.kodi.utils import ADDON_PROFILE_PATH
from lib.vendor.segno import make as segnomake

import xbmcgui


def make_qrcode(url):
    if not url:
        return
    try:
        art_path = path.join(ADDON_PROFILE_PATH, "qr.png")
        kodilog(f"Creating QR code for URL: {art_path}")
        qrcode = segnomake(url, micro=False)
        qrcode.save(art_path, scale=20)
        return art_path
    except Exception as e:
        kodilog("Error creating QR code: %s", e)


class QRProgressDialogLib(xbmcgui.WindowDialog):
    def __init__(self, title, qr_path, auth_url, user_code):
        super().__init__()
        # Use skin base res (Kodi scales this to actual screen)
        screen_w, screen_h = 1280, 720

        box_w, box_h = 600, 400
        box_x = (screen_w - box_w) // 2  # 340
        box_y = (screen_h - box_h) // 2  # 160

        # Background
        self.bg = xbmcgui.ControlImage(
            box_x,
            box_y,
            box_w,
            box_h,
            path.join(ADDON_PATH, "resources", "img", "texture.png"),
        )
        self.addControl(self.bg)

        # Title
        self.title_lbl = xbmcgui.ControlLabel(
            box_x + 20, box_y + 20, box_w - 40, 30, f"[B]{title}[/B]"
        )
        self.addControl(self.title_lbl)

        # QR
        self.qr = xbmcgui.ControlImage(box_x + 30, box_y + 70, 200, 200, qr_path)
        self.addControl(self.qr)

        # Instructions
        self.text_lbl = xbmcgui.ControlLabel(
            box_x + 250,
            box_y + 70,
            box_w - 280,
            120,
            f"Go to:\n[COLOR cyan]{auth_url}[/COLOR]\n\n"
            f"Enter code:\n[COLOR seagreen][B]{user_code}[/B][/COLOR]",
        )
        self.addControl(self.text_lbl)

        # Progress bar
        self.progress = xbmcgui.ControlProgress(box_x + 20, box_y + 300, box_w - 40, 30)
        self.addControl(self.progress)

        # Cancel button
        self.cancel_btn = xbmcgui.ControlButton(
            box_x + box_w - 140, box_y + box_h - 40, 120, 30, "Cancel"
        )
        self.addControl(self.cancel_btn)

    def setProgress(self, percent, message=""):
        self.progress.setPercent(percent)
        if message:
            self.text_lbl.setLabel(message)

    def isCanceled(self):
        return self.getFocusId() == self.cancel_btn.getId()
