from lib.utils.general.utils import supported_video_extensions
from lib.utils.kodi.utils import dialogyesno, notification, sleep as ksleep, translation
from xbmcgui import DialogProgress


DEBRID_ERROR_STATUS = ("magnet_error", "error", "virus", "dead")


def run_realdebrid_download(client, magnet_url, pack=False):
    interval = 5
    cancelled = False
    response = client.add_magnet_link(magnet_url)
    if not response:
        return

    torrent_id = response["id"]
    progress_dialog = DialogProgress()
    torrent_info = client.get_torrent_info(torrent_id)
    if not torrent_info:
        return

    status = torrent_info["status"]
    if status == "magnet_conversion":
        msg = translation(90638) % torrent_info["filename"]
        progress_timeout = 100
        progress_dialog.create(translation(90565))
        while status == "magnet_conversion" and progress_timeout > 0:
            progress_dialog.update(progress_timeout, msg)
            if progress_dialog.iscanceled():
                cancelled = True
                break
            progress_timeout -= interval
            ksleep(1000 * interval)
            torrent_info = client.get_torrent_info(torrent_id)
            status = torrent_info["status"]
            if any(error in status for error in DEBRID_ERROR_STATUS):
                notification(translation(90639))
                break
    elif status == "downloaded":
        notification(translation(90640))
        return
    elif status == "waiting_files_selection":
        cancelled = _handle_waiting_file_selection(
            client, torrent_id, torrent_info, progress_dialog, interval, pack
        )

    try:
        progress_dialog.close()
    except Exception:
        pass

    ksleep(500)
    if cancelled:
        response = dialogyesno(
            translation(32029), translation(90564)
        )
        if response:
            notification(translation(90641))
        else:
            client.delete_torrent(torrent_id)


def _handle_waiting_file_selection(
    client, torrent_id, torrent_info, progress_dialog, interval, pack
):
    files = torrent_info["files"]
    extensions = supported_video_extensions()[:-1]
    items = [
        item
        for item in files
        for extension in extensions
        if item["path"].lower().endswith(extension)
    ]
    try:
        video = max(items, key=lambda item: item["bytes"])
        file_id = video["id"]
    except ValueError as error:
        notification(error)
        return False

    client.select_files(torrent_id, str(file_id))
    ksleep(2000)
    torrent_info = client.get_torrent_info(torrent_id)
    if not torrent_info:
        return False

    status = torrent_info["status"]
    if status == "downloaded":
        notification(translation(90642))
        return False

    file_size = round(float(video["bytes"]) / (1000**3), 2)
    msg = translation(90643) % torrent_info["filename"]
    progress_dialog.create(translation(90565))
    progress_dialog.update(1, msg)
    while status != "downloaded":
        ksleep(1000 * interval)
        torrent_info = client.get_torrent_info(torrent_id)
        status = torrent_info["status"]
        if status == "downloading":
            msg2 = translation(90644) % (
                file_size,
                round(float(torrent_info["speed"]) / (1000**2), 2),
                torrent_info["seeders"],
                torrent_info["progress"],
            )
        else:
            msg2 = status
        progress_dialog.update(int(float(torrent_info["progress"])), msg + msg2)
        try:
            if progress_dialog.iscanceled():
                return True
        except Exception:
            pass
        if any(error in status for error in DEBRID_ERROR_STATUS):
            notification(translation(90639))
            break
    return False
