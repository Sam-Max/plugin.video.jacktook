from http import HTTPStatus
import json
from time import sleep, time
import requests
from lib.api.jacktook.kodi import kodilog
from lib.api.plex.settings import settings
from lib.api.plex.models.plex_models import AuthPin, PlexUser
from lib.api.plex.utils import HTTPException, PlexUnauthorizedError
from lib.utils.kodi_utils import copy2clip, dialog_ok, progressDialog, set_setting


class PlexApi:
    def __init__(self) -> None:
        self.PLEX_AUTH_URL = "https://app.plex.tv/auth#?"
        self.PLEX_API_URL = "https://plex.tv/api/v2"
        self.client = requests.Session()
        self.headers = {"accept": "application/json"}
        self.auth_token = None

    def login(self):
        auth_pin = self.create_auth_pin()
        copy2clip(auth_pin.code)
        content = "%s[CR]%s" % (
            f"Navigate to: [B]https://www.plex.tv/link[/B]",
            f"and enter the code: [COLOR seagreen][B]{auth_pin.code}[/B][/COLOR] "
        )
        progressDialog.create("Plex Auth")
        progressDialog.update(-1, content)
        kodilog("Start polling plex.tv for token")
        start_time = time()
        while time() - start_time < 300:
            auth_token = self.get_auth_token(auth_pin)
            if auth_token is not None:
                self.auth_token = auth_token
                set_setting("plex_token", self.auth_token)
                progressDialog.close()
                dialog_ok("Success", "Authentication completed.")
                return True
            if progressDialog.iscanceled():
                progressDialog.close()
                return False
            sleep(1)
        else:
            progressDialog.close()
            dialog_ok("Error:", "Pin timed out.")
            return False

    def create_auth_pin(self) -> AuthPin:
        response = self.client.post(
            f"{self.PLEX_API_URL}/pins",
            data={
                "strong": "false",
                "X-Plex-Product": settings.product_name,
                "X-Plex-Client-Identifier": settings.identifier,
            },
            headers=self.headers,
            timeout=settings.plex_requests_timeout,
        )
        json = response.json()
        return AuthPin(**json)

    def get_auth_token(self, auth_pin):
        json = self.get_json(
            url=f"{self.PLEX_API_URL}/pins/{auth_pin.id}",
            params={
                "code": auth_pin.code,
                "X-Plex-Client-Identifier": settings.identifier,
            },
        )
        return json["authToken"]

    def get_json(self, url, params=None):
        if params is None:
            params = {}
        try:
            response = self.client.get(
                url,
                params=params,
                headers=self.headers,
                timeout=settings.plex_requests_timeout,
            )
            if response.status_code in (401, 403):
                raise PlexUnauthorizedError()
            if response.status_code >= 400:
                raise HTTPException(
                    status_code=502,
                    detail="Received error from plex server",
                )
            return json.loads(response.content)
        except TimeoutError:
            raise HTTPException(
                status_code=504,
                detail="Plex server timeout error",
            )

    def get_plex_user(self):
        response = self.client.get(
            f"{self.PLEX_API_URL}/user",
            params={
                "X-Plex-Product": settings.product_name,
                "X-Plex-Client-Identifier": settings.identifier,
                "X-Plex-Token": self.auth_token,
            },
            headers=self.headers,
            timeout=settings.plex_requests_timeout,
        )
        if response.status_code != HTTPStatus.OK:
            return
        json = response.json()
        return PlexUser(**json)

    def logout(self):
        self.auth_token = ""
        set_setting("plex_token", "")
        try:
            self.client.close()
        except:
            pass
        self.client = None
        set_setting("plex_user", "")
        set_setting("plex_server_name", "")
        set_setting("plex_discovery_url", "")
        set_setting("plex_streaming_url", "")
        set_setting("plex_token", "")
        set_setting("plex_server_token", "")

