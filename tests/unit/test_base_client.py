from unittest.mock import patch

from lib.clients.base import BaseClient


class _DummyClient(BaseClient):
    def search(self, *args, **kwargs):
        return []

    def parse_response(self, res):
        return []


def test_handle_exception_redacts_api_key_in_log():
    client = _DummyClient("http://localhost", None)
    message = (
        "Search error: HTTPSConnectionPool(host='jac.red', port=9117): Max retries "
        "exceeded with url: /api/v2.0/indexers/all/results/torznab/api"
        "?apikey=SECRET123&q=Dune (Caused by NewConnectionError(...))"
    )

    logged = []
    with patch(
        "lib.clients.base.kodilog",
        side_effect=lambda msg, level=None: logged.append(msg),
    ):
        with patch("lib.clients.base.notification"):
            client.handle_exception(message)

    assert "SECRET123" not in logged[0]
    assert "apikey=***" in logged[0]
    assert "q=Dune" in logged[0]


def test_handle_exception_redacts_api_key_in_notification():
    client = _DummyClient("http://localhost", None)

    with patch("lib.clients.base.kodilog"):
        with patch("lib.clients.base.notification") as notify:
            client.handle_exception("Error /api?apikey=SECRET123&q=Dune")

    assert "SECRET123" not in notify.call_args.args[0]
    assert "apikey=***" in notify.call_args.args[0]
