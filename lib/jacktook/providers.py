from lib.jacktook.provider_base import (
    ProviderResult,
    get_providers,
    send_to_providers,
)
from lib.jacktook.listener import ProviderListenerDialog
from lib.jacktook.utils import NoProvidersError
from lib.utils.kodi.utils import kodilog


def burst_search(query):
    return search("search", query)


def burst_search_movie(movie_id, query):
    return search("search_movie", movie_id, query)


def burst_search_show(show_id, query):
    return search("search_show", show_id, query)


def burst_search_season(show_id, show_title, season_number):
    return search("search_season", show_id, show_title, int(season_number))


def burst_search_episode(show_id, query, season_number, episode_number):
    return search(
        "search_episode", show_id, query, int(season_number), int(episode_number)
    )


def search(method, *args, **kwargs):
    providers = get_providers()
    if not providers:
        raise NoProvidersError("No providers available")
    with ProviderListenerDialog(providers, method, timeout=30) as listener:
        send_to_providers(providers, method, *args, **kwargs)
    results = []
    for provider, provider_results in listener.data.items():
        if not isinstance(provider_results, (tuple, list)):
            kodilog(f"Expecting list/tuple from {provider}:{method}")
            continue
        for provider_result in provider_results:
            try:
                results.append(ProviderResult(provider_result))
            except Exception as e:
                kodilog(f"Invalid result from {provider}: {e}")
    if not results:
        raise Exception("No results found")
    return results
