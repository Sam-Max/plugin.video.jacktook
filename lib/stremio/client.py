import requests
from lib.utils.utils import USER_AGENT_HEADER
from lib.api.jacktook.kodi import kodilog

class Stremio:
    def __init__(self, authKey=None):
        self.authKey = authKey
        self.session = requests.Session()
        self.session.headers.update(USER_AGENT_HEADER)

    def _post(self, url, data):
        return self.session.post(url, json=data, headers=USER_AGENT_HEADER, timeout=10).json()
    
    def _get(self, url):
        resp = self.session.get(url, headers=USER_AGENT_HEADER, timeout=10)
        return resp.json()

    def login(self, email, password):
        """Login to Stremio account."""
  
        data = {"authKey":self.authKey,
                "email":email,
                "password":password,
                }
        
        res =  self._post('https://api.strem.io/api/login', data)
        self.authKey=res.get('result', {}).get('authKey', None)
        
    def dataExport(self):
        """Export user data."""
        assert self.authKey, "Login first"
        data = {"authKey":self.authKey}
        res=self._post('https://api.strem.io/api/dataExport', data)
        exportId=res.get('result', {}).get('exportId', None)
        
        dataExport=self._get(f'https://api.strem.io/data-export/{exportId}/export.json')
        return dataExport
    
    def get_community_addons(self):
        """Get community addons."""
        response = self._get("https://stremio-addons.com/catalog.json")
        return response
    
    def get_my_addons(self):
        """Get user addons."""
        response = self.dataExport()
        return response.get('addons', {}).get('addons', [])