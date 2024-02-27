from resources.lib.utils.kodi import log
from xbmcgui import DialogProgress
from routing import Plugin
from xbmcgui import ListItem

# * ill get rid of the unused imports soon before any PR

plugin = Plugin()

@plugin.route("/download")
def download_to_disk(url: str):
    log("PLEASE")
    # TODO implement progress dialog
    # progress_dialogue = DialogProgress()
    
    # TODO implement logic for grabbing direct URL by result info from debrid api, just support cached RD results to start with
    log(url)
    
