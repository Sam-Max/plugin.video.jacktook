from .utils import NoProvidersError
from .provider_base import ProviderListener
from lib.utils.kodi.utils import ADDON_NAME
from xbmcgui import DialogProgressBG


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
