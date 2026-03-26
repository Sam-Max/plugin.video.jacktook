from time import time

from lib.gui.qr_progress_dialog import QRProgressDialog
from lib.jacktook.utils import ADDON_PATH
from lib.utils.debrid.qrcode_utils import make_qrcode
from lib.utils.general.utils import DebridType
from lib.utils.kodi.utils import (
    copy2clip,
    dialog_ok,
    progressDialog,
    set_setting,
    sleep as ksleep,
    translation,
)


def run_realdebrid_auth(client):
    response = client.get_device_code()
    if not response:
        return

    sleep_interval = int(response["interval"])
    expires_in = int(response["expires_in"])
    device_code = response["device_code"]
    user_code = response["user_code"]
    auth_url = response["direct_verification_url"]

    qr_code = make_qrcode(auth_url)
    copy2clip(auth_url)

    progress_dialog = QRProgressDialog("qr_dialog.xml", ADDON_PATH)
    progress_dialog.setup(
        translation(90594),
        qr_code,
        auth_url,
        user_code,
        DebridType.RD,
    )
    progress_dialog.show_dialog()

    start_time = time()
    while time() - start_time < expires_in:
        ksleep(1000 * sleep_interval)
        if progress_dialog.iscanceled:
            progress_dialog.close_dialog()
            return
        try:
            auth_response = client.authorize(device_code)
        except Exception:
            continue
        try:
            if "token" in auth_response:
                client.token = auth_response["token"]
                set_setting("real_debrid_token", client.token)
                set_setting("real_debid_authorized", "true")

                client.initialize_headers()

                set_setting("real_debrid_user", client.get_user()["username"])
                progress_dialog.update_progress(100, translation(90545))
                progress_dialog.close_dialog()
                return

            elapsed = time() - start_time
            percent = int((elapsed / expires_in) * 100)
            progress_dialog.update_progress(percent)
        except Exception as error:
            progress_dialog.close_dialog()
            dialog_ok(translation(90548), translation(90547) % error)
            return


def run_alldebrid_auth(client):
    response = client.get_ping()
    result = response["data"]

    expires_in = int(result["expires_in"])
    sleep_interval = 5
    user_code = result["pin"]
    check_id = result["check"]
    user_url = result["user_url"]

    qr_code = make_qrcode(user_url)
    copy2clip(user_url)

    progress_dialog = QRProgressDialog("qr_dialog.xml", ADDON_PATH)
    progress_dialog.setup(
        translation(90604) % DebridType.AD,
        qr_code,
        user_url,
        user_code,
        DebridType.AD,
    )
    progress_dialog.show_dialog()

    start_time = time()
    while time() - start_time < expires_in and not client.token:
        ksleep(1000 * sleep_interval)
        if progress_dialog.iscanceled:
            progress_dialog.close_dialog()
            return
        response = client.poll_auth(check_id, user_code)
        if not response["activated"]:
            elapsed = time() - start_time
            percent = int((elapsed / expires_in) * 100)
            progress_dialog.update_progress(percent)
            continue
        try:
            if "apikey" in response:
                client.token = response.get("apikey", "")
                set_setting("alldebrid_token", client.token)
                set_setting("alldebrid_authorized", "true")

                client.initialize_headers()

                user = client.get_user_info()
                set_setting("alldebrid_user", str(user["user"]["username"]))

                progress_dialog.update_progress(100, translation(90545))
                progress_dialog.close_dialog()
                return

            elapsed = time() - start_time
            percent = int((elapsed / expires_in) * 100)
            progress_dialog.update_progress(percent)
        except Exception as error:
            progress_dialog.close_dialog()
            dialog_ok(translation(90548), translation(90547) % error)
            return


def run_premiumize_auth(client):
    response = client.get_device_code()
    user_code = response["user_code"]
    copy2clip(user_code)
    content = "%s[CR]%s[CR]%s" % (
        translation(90540),
        translation(90541) % response.get("verification_uri"),
        translation(90542) % user_code,
    )
    progressDialog.create(translation(90543))
    progressDialog.update(-1, content)

    device_code = response["device_code"]
    expires_in = int(response["expires_in"])
    sleep_interval = int(response["interval"])
    start_time = time()
    time_passed = 0

    while not progressDialog.iscanceled() and time_passed < expires_in:
        ksleep(1000 * sleep_interval)
        auth_response = client.authorize(device_code)
        if "error" in auth_response:
            time_passed = time() - start_time
            progress = int(100 * time_passed / float(expires_in))
            progressDialog.update(progress, content)
            continue
        try:
            progressDialog.close()
            client.token = str(auth_response["access_token"])
            set_setting("premiumize_token", client.token)
            dialog_ok(translation(90544), translation(90545))
            return
        except Exception as error:
            dialog_ok(translation(90546), translation(90547) % error)
            break

    try:
        progressDialog.close()
    except Exception:
        pass


def run_torbox_auth(client):
    response = client.get_device_code()
    if not response or not response.get("success"):
        return

    data = response.get("data", {})
    sleep_interval = int(data.get("interval", 5))
    expires_in = int(data.get("expires_in", 600))
    device_code = data.get("device_code")
    user_code = data.get("code")
    auth_url = data.get("verification_url")
    friendly_url = data.get("friendly_verification_url") or auth_url

    qr_code = make_qrcode(auth_url)
    copy2clip(auth_url)

    progress_dialog = QRProgressDialog("qr_dialog.xml", ADDON_PATH)
    progress_dialog.setup(
        translation(90595),
        qr_code,
        friendly_url,
        user_code,
        DebridType.TB,
    )
    progress_dialog.show_dialog()

    start_time = time()
    while time() - start_time < expires_in:
        ksleep(1000 * sleep_interval)
        if progress_dialog.iscanceled:
            progress_dialog.close_dialog()
            return
        try:
            auth_response = client.authorize(device_code)
        except Exception:
            continue
        try:
            if "token" in auth_response:
                client.token = auth_response["token"]
                set_setting("torbox_token", client.token)
                set_setting("torbox_enabled", "true")

                client.initialize_headers()

                user_data = client.get_user()
                if user_data.get("success"):
                    set_setting(
                        "torbox_user",
                        user_data.get("data", {}).get("email", ""),
                    )

                progress_dialog.update_progress(100, translation(90545))
                progress_dialog.close_dialog()
                dialog_ok(translation(90544), translation(90549))
                return

            elapsed = time() - start_time
            percent = int((elapsed / expires_in) * 100)
            progress_dialog.update_progress(percent)
        except Exception as error:
            progress_dialog.close_dialog()
            dialog_ok(translation(90548), translation(90547) % error)
            return


def run_debrider_auth(client):
    response = client.get_device_code()
    if not response:
        return

    interval = int(response["interval"])
    expires_in = int(response["expires_in"])
    device_code = response["device_code"]
    user_code = response["user_code"]
    auth_url = response["verification_url"]
    qr_code = make_qrcode(auth_url)
    copy2clip(auth_url)

    progress_dialog = QRProgressDialog("qr_dialog.xml", ADDON_PATH)
    progress_dialog.setup(translation(90596), qr_code, auth_url, user_code, DebridType.DB)
    progress_dialog.show_dialog()

    start_time = time()
    while time() - start_time < expires_in:
        if progress_dialog.iscanceled:
            progress_dialog.close_dialog()
            return
        elapsed = time() - start_time
        percent = int((elapsed / expires_in) * 100)
        progress_dialog.update_progress(percent)
        try:
            auth_response = client.get_device_auth_status(device_code)
            if "apikey" in auth_response:
                client.token = auth_response["apikey"]
                progress_dialog.close_dialog()
                set_setting("debrider_token", client.token)
                set_setting("debrider_authorized", "true")
                client.initialize_headers()
                dialog_ok(translation(90544), translation(90545))
                return
            ksleep(1000 * interval)
        except Exception as error:
            progress_dialog.close_dialog()
            dialog_ok(translation(90546), translation(90547) % error)
            return
