from lib.api.jacktook.kodi import kodilog
from lib.api.plex.media_server_api import check_server_connection, get_servers
from lib.api.plex.plex_api import PlexApi
from lib.utils.kodi_utils import get_setting, set_setting
from xbmcgui import Dialog

plex = PlexApi()

server_config = {"discoveryUrl": [], "streamingUrl": []}

def plex_login():
    success = plex.login()
    if success:
        user = plex.get_plex_user()
        if user:
            set_setting("plex_user", user.username)
        

def validate_server():
    servers = get_servers("https://plex.tv/api/v2", get_setting("plex_token"))
    if servers:
        server_names = [s.name for s in servers]
        chosen_server = Dialog().select("Select server", server_names)
        if chosen_server < 0:
            return
        for s in servers:
            if s.name == server_names[chosen_server]:
                set_setting("plex_server_name", s.name)
                set_setting("plex_server_token", s.access_token)
                for c in s.connections:
                    server_config["streamingUrl"].append(c["uri"])
                    if c["local"] is not True:
                        server_config["discoveryUrl"].append(c["uri"])
                break
    discovery_test(server_config["discoveryUrl"], get_setting("plex_server_token"))
    streaming_test(server_config["streamingUrl"], get_setting("plex_server_token"))


def discovery_test(urls, access_token):
    kodilog("Making discovery test...")
    kodilog(urls)
    for url in urls:
        success = check_server_connection(url, access_token)
        if success:
            set_setting("plex_discovery_url", url)
            break


def streaming_test(urls, access_token):
    kodilog("Making streaming test...")
    kodilog(urls)
    for url in urls:
        success = check_server_connection(url, access_token)
        if success:
            set_setting("plex_streaming_url", url)
            break

def plex_logout():
    plex.logout()