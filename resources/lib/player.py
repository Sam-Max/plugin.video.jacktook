from resources.lib.kodi import hide_busy_dialog, notify
from xbmc import Player as xbmc_player


class JacktookPlayer(xbmc_player):
    def __init__(self):
        xbmc_player.__init__(self)

    def run(self, list_item=None):
        hide_busy_dialog()
        if not self.url:
            return self.run_error()
        try:
            return self.play_video(list_item)
        except:
            return self.run_error()

    def play_video(self, list_item):
        self.play(self.url, list_item)

    def make_listing(self, listitem, url, title, imdb_id):
        self.set_constants(url)
        listitem.setContentLookup(False)
        
        info_tag = listitem.getVideoInfoTag()
        info_tag.setMediaType("video")
        info_tag.setFilenameAndPath(self.url)
        info_tag.setTitle(title)
        info_tag.setIMDBNumber(imdb_id)
        info_tag.setUniqueIDs(
            {"imdb": str(imdb_id), "tmdb": str(imdb_id), "tvdb": str(imdb_id)}
        )
        return listitem

    def set_constants(self, url):
        self.url = url

    def run_error(self):
        notify("Playback Failed")
        return False
