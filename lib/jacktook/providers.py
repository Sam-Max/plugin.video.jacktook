from .provider_base import (
    ProviderResult,
    get_providers,
    send_to_providers,
)
from .listener import ProviderListenerDialog
from .utils import NoProvidersError
from ..utils.kodi.utils import kodilog


def burst_search(query, silent=False):
    return search("search", query, silent=silent)


def burst_search_movie(movie_id, query, silent=False):
    return search("search_movie", movie_id, query, silent=silent)


def burst_search_show(show_id, query, silent=False):
    return search("search_show", show_id, query, silent=silent)


def burst_search_season(show_id, show_title, season_number, silent=False):
    return search(
        "search_season", show_id, show_title, int(season_number), silent=silent
    )


def burst_search_episode(show_id, query, season_number, episode_number, silent=False):
    return search(
        "search_episode",
        show_id,
        query,
        int(season_number),
        int(episode_number),
        silent=silent,
    )


def search(method, *args, **kwargs):
    silent = kwargs.pop("silent", False)
    providers = get_providers()
    if not providers:
        raise NoProvidersError("No providers available")

    with ProviderListenerDialog(
        providers, method, timeout=30, silent=silent
    ) as listener:
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