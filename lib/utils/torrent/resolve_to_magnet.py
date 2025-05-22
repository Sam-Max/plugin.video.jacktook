import requests
from lib.utils.general.utils import USER_AGENT_HEADER



def resolve_to_magnet(url):
    """
    Perform a GET request to the URL and check if it redirects to a magnet
    
    Args:
        url (str): The URL to check.
    
    Returns:
        str: The magnet URL if the URL points or redirects to a magnet
        
    """
    if url.startswith('magnet:?'):
        return url

    try:
        response = requests.get(url, headers=USER_AGENT_HEADER, timeout=10, allow_redirects=False, stream=True)
        is_redirect = response.is_redirect or response.is_permanent_redirect
        redirect_location = response.headers.get('Location') if is_redirect else None
        
        if is_redirect and redirect_location.startswith('magnet:?'):
            return redirect_location
    except requests.RequestException as e:
        return None
    finally:
        try:
            response.close()
        except NameError:
            pass # Response not defined if an exception occurred before the request

    return None