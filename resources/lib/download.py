from resources.lib.utils.kodi import log, get_setting
from xbmcgui import DialogProgress
from routing import Plugin
import urllib.request

plugin = Plugin()

@plugin.route("/download")
def download_to_disk(url: str):
    # TODO implement progress dialog
    progress_dialogue = DialogProgress()
    selected_dir = get_setting("download_dir")
    if selected_dir:
        download_hopefully(url, f"{selected_dir}/filename2", progress_dialogue)
    else:
        # ! THROW ERROR ABOUT DOWNLOAD DIR
        log("no download dir please do download dir")

# ! RENAME FUNCTION PLEASE
def download_hopefully(url, filename, progressbar: DialogProgress):
    try:
        req = urllib.request.urlopen(url)
        total_size = int(req.getheader('Content-Length')) if req.getheader('Content-Length') else None
        downloaded = 0

        with open(filename, "wb") as file:
            progressbar.create("Local Download")
            while True:
                chunk = req.read(1024)
                if not chunk:
                    break
                downloaded += len(chunk)
                file.write(chunk)
                if total_size:
                    progress = downloaded * 100 / total_size
                    log(f"Downloading... Progress: {int(progress)}%") 
                    progressbar.update(int(progress), f"Progress: {progress:.2f}%")
                else:
                    log(f"Downloaded {downloaded} bytes...")
                    progressbar.close()
        log("\nDownload complete.")
        # ? Return something?
    except Exception as e:
        log(e)
            
