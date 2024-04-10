import logging
from lib.utils.kodi import ADDON_NAME, log, notify
from xbmcgui import DialogProgressBG
from lib.api.jacktook.provider import (
    get_providers,
    send_to_providers,
    ProviderListener,
    ProviderResult,
)


class ResolveTimeoutError(Exception):
    pass


class NoProvidersError(Exception):
    pass


class ProviderListenerDialog(ProviderListener):
    def __init__(self, providers, method, timeout=10):
        super(ProviderListenerDialog, self).__init__(providers, method, timeout=timeout)
        self._total = len(providers)
        self._count = 0
        self._dialog = DialogProgressBG()

    def on_receive(self, sender):
        self._count += 1
        self._dialog.update(int(100 * self._count / self._total))

    def __enter__(self):
        ret = super(ProviderListenerDialog, self).__enter__()
        self._dialog.create(ADDON_NAME, "Getting results from providers...")
        return ret

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            return super(ProviderListenerDialog, self).__exit__(
                exc_type, exc_val, exc_tb
            )
        finally:
            self._dialog.close()


def run_providers_method(timeout, method, *args, **kwargs):
    providers = get_providers()
    if not providers:
        raise NoProvidersError("No available providers")
    with ProviderListenerDialog(providers, method, timeout=timeout) as listener:
        send_to_providers(providers, method, *args, **kwargs)
    return listener.data


def run_provider_method(provider, timeout, method, *args, **kwargs):
    with ProviderListener((provider,), method, timeout=timeout) as listener:
        send_to_providers((provider,), method, *args, **kwargs)
    try:
        return listener.data[provider]
    except KeyError:
        raise ResolveTimeoutError("Timeout reached")


def get_providers_results(method, *args, **kwargs):
    results = []
    data = run_providers_method(30, method, *args, **kwargs)
    for provider, provider_results in data.items():
        if not isinstance(provider_results, (tuple, list)):
            logging.error(
                "Expecting list or tuple as results for %s:%s", provider, method
            )
            continue
        for provider_result in provider_results:
            try:
                _provider_result = ProviderResult(provider_result)
            except Exception as e:
                logging.error(
                    "Invalid format on provider '%s' result (%s): %s",
                    provider,
                    provider_result,
                    e,
                )
            else:
                results.append((provider, _provider_result))
    return results


def search(method, *args, **kwargs):
    try:
        results = get_providers_results(method, *args, **kwargs)
    except NoProvidersError:
        results = None
    if results:
        return results
    elif results is None:
        notify("No providers available")
    else:
        notify("No results found!")


def burst_search(query):
    return search("search", query)


def burst_search_movie(movie_id, query, titles="", year=None):
    return search(
        "search_movie",
        movie_id,
        query,
        titles,
        year=year,
    )


def burst_search_show(show_id, query, titles="", year=None):
    return search(
        "search_show",
        show_id,
        query,
        titles,
        year=year,
    )


def burst_search_season(show_id, show_title, season_number, titles):
    return search(
        "search_season",
        show_id,
        show_title,
        int(season_number),
        titles
    )


def burst_search_episode(show_id, query, season_number, episode_number, titles=""):
    return search(
        "search_episode",
        show_id,
        query,
        int(season_number),
        int(episode_number),
        titles,
    )
