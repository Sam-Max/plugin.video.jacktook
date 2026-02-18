# -*- coding: utf-8 -*-
from lib.services.webserver import StremioWebServer, get_local_ip
from lib.utils.debrid.qrcode_utils import make_qrcode
from lib.gui.qr_progress_dialog import QRProgressDialog
from lib.utils.kodi.utils import ADDON_PATH, kodilog


_SERVER_PORT = 8081


def stremio_manage_phone(params):
    local_ip = get_local_ip()
    url = f"http://{local_ip}:{_SERVER_PORT}/"

    server = StremioWebServer(port=_SERVER_PORT)
    server.start()

    if not server.is_running:
        from lib.utils.kodi.utils import notification

        notification("Failed to start web server. Port may be in use.")
        return

    try:
        kodilog(f"Server started at {url}")

        # Generate QR code image
        qr_path = make_qrcode(url)

        # Show blocking QR dialog
        dialog = QRProgressDialog("qr_dialog.xml", ADDON_PATH)
        dialog.setup(
            title="Manage from Phone",
            qr_code=qr_path or "",
            url=url,
            user_code="",
            is_debrid=False,
        )
        dialog.doModal()
    finally:
        server.stop()
        kodilog("Server stopped")
