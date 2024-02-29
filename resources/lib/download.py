from resources.lib.utils.kodi import log, get_setting
from xbmcgui import DialogProgressBG
from routing import Plugin
import os
from urllib import request, parse
plugin = Plugin()


@plugin.route("/download")
def download_to_disk(url: str, title: str):
    # TODO implement progress dialog
    selected_dir = get_setting("download_dir")
    if selected_dir:
        download_hopefully(url, f"{selected_dir}/{title}{get_extension(url)}", title, DialogProgressBG())
    else:
        # ! THROW ERROR ABOUT DOWNLOAD DIR
        log("no download dir please do download dir")



def download_hopefully(url: str, filename: str, title: str, progressbar: DialogProgressBG):
    try:
        log(url)
        req = request.urlopen(url)
        total_size = int(req.getheader('Content-Length')
                         ) if req.getheader('Content-Length') else None
        downloaded = 0

        with open(filename, "wb") as file:
            progressbar.create("Local Download", f"Downloading: {title}")
            while True:
                chunk = req.read(1024)
                if not chunk:
                    break
                if progressbar.isFinished():
                    progressbar.close()
                downloaded += len(chunk)
                file.write(chunk)
                if total_size:
                    progress = downloaded * 100 / total_size
                    progressbar.update(
                        int(progress))
                else:
                    log(f"Downloaded {downloaded} bytes...")
                    progressbar.close()
        log("\nDownload complete.")

        # ? Return something?
    except Exception as e:
        log(e)

def get_extension(url):
    parsed_url = parse.urlparse(url)
    path = parsed_url.path
    filename, extension = os.path.splitext(path)
    return extension.lower()
