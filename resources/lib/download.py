from resources.lib.utils.kodi import log
from xbmcgui import DialogProgress

# * ill get rid of the unused imports soon before any PR
def download_to_disk(list_item, res, cached=True):
    log("PLEASE")
    # TODO implement progress dialog
    progress_dialogue = DialogProgress()
    
    # TODO implement logic for grabbing direct URL by result info from debrid api, just support cached RD results  to start with
    url = res["title"]
    log(url)
    
