from resources.lib.utils.kodi import log
from xbmcgui import DialogProgress
from routing import Plugin
from xbmcgui import ListItem
from time import sleep
import requests
import urllib.request
# * ill get rid of the unused imports soon before any PR

plugin = Plugin()

@plugin.route("/download")
def download_to_disk(url: str):
    log("PLEASE")
    # TODO implement progress dialog
    progress_dialogue = DialogProgress()
    
    # TODO implement logic for grabbing direct URL by result info from debrid api, just support cached RD results to start with
    log(url)
    
    download_hopefully(url, r"C:\\Users\\Sam\\Documents\\filename", progress_dialogue)

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
                    log(f"Downloading... Progress: {progress}%") 
                    progressbar.update(int(progress), f"Progress: {progress:.2f}%")
                else:
                    log(f"Downloaded {downloaded} bytes...")
                    progressbar.close()
        log("\nDownload complete.")
        # ? Return something?
    except Exception as e:
        log(e)
            
