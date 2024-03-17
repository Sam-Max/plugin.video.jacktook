from resources.lib.utils.kodi import log, get_setting
from xbmcgui import DialogProgressBG
from routing import Plugin
from threading import Thread, enumerate
import os
from urllib import request, parse
from resources.lib.db.database import get_db
from time import sleep


class DownloadManager:
    def __init__(self):
        self.plugin = Plugin()

        if not get_db().get_dm('jt:dlm', 'queue') == None:
            self.queue = get_db().get_dm('jt:dlm', 'queue')
            if not type(self.queue) == list:
                self.queue = []
                # ! THROW UI ERROR
                get_db().set_dm('jt:dlm', 'queue', self.queue)
        else:
            self.queue = []
            log(f"Queue: {type(self.queue)}")

        if not get_db().get_dm('jt:dlm', 'active_downloads') == None:
            self.active_downloads: dict = get_db().get_dm('jt:dlm', 'active_downloads')
            log(f"Downloads: {type(self.queue)}")
            if not type(self.active_downloads) == dict:
                self.active_downloads = {}
                # ! THROW UI ERROR
                get_db().set_dm('jt:dlm', 'active', self.active_downloads)
        else:
            self.active_downloads = {}
            log(f"Downloads: {type(self.queue)}")
        
        try:
            for key in self.active_downloads:
                download_info = [self.active_downloads[key]['url'],
                                self.active_downloads[key]['title'],
                                self.active_downloads[key]['filename']]
                self.queue.insert(0, download_info)
        finally:
            self.active_downloads.clear()

        self.start_downloads()

    def add_to_queue(self, url: str, title: str):
        selected_dir = get_setting("download_dir")
        if not selected_dir:
            # ! THROW UI ERROR
            return

        filename = f"{selected_dir}/{title}{self.get_extension(url)}"
        download_info = [url, title, filename]
        self.queue.append(download_info)
        self.start_downloads()

    def start_downloads(self):
        while self.queue and len(self.active_downloads) < 2:  # Adjust limit as needed
            download_info = self.queue.pop(0)
            log(f"{self.queue}, {self.active_downloads}")
            download_info = {
                'url': download_info[0],
                'title': download_info[1],
                'filename': download_info[2]
            }
            self.active_downloads[download_info["url"]] = download_info
            thread = Thread(target=self.download_to_local,
                            args=(download_info,), daemon=True, name=download_info["url"])
            thread.start()

        get_db().set_dm('jt:dlm', 'active', self.active_downloads)
        get_db().set_dm('jt:dlm', 'queue', self.queue)

    def download_to_local(self, download_info):
        try:
            req = request.urlopen(download_info["url"])
            total_size = int(req.getheader("Content-Length")
                             ) if req.getheader("Content-Length") else None
            downloaded = 0
            with open(download_info["filename"], "wb") as file:
                progressbar = DialogProgressBG()
                progressbar.create(
                    "Debrid to Local Download", f"Downloading: {download_info['title']}")
                progressbar.deallocating
                while True:
                    chunk = req.read(1024)
                    if not chunk:
                        break
                    if not self.active_downloads[download_info['url']]:
                        break
                    downloaded += len(chunk)
                    file.write(chunk)
                    progress = int(
                        downloaded * 100 / total_size) if total_size else downloaded
                    progressbar.update(message=f"Downloading: {progress}% - {download_info['title']}")
                    if progress == 100:
                        sleep(3)
                        break
                progressbar.close()
                del self.active_downloads[download_info['url']]
                self.start_downloads()  # * Start next in queue after finishing
        except Exception as e:
            log(e)
            # ! Throw UI Error!!
            del self.active_downloads[download_info['url']]
            self.start_downloads()  # * Start next in queue even on error

    @staticmethod
    def get_extension(url):
        parsed_url = parse.urlparse(url)
        path = parsed_url.path
        filename, extension = os.path.splitext(path)
        return extension.lower()

    def cancel_download(self, url):
        del self.active_downloads['url']
        sleep(3)
        # ! THROW UI OUTPUT
        log("Cancelled and file deleted.")


download_manager = DownloadManager()


def get_dlm():
    return download_manager


def download_to_disk(url, title):
    download_manager.add_to_queue(url, title)
