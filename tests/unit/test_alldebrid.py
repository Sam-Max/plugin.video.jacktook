from unittest.mock import MagicMock

from lib.api.debrid.alldebrid import AllDebrid


def _client_with_mock_session() -> AllDebrid:
    client = AllDebrid(token="test-token")
    client.session = MagicMock()
    return client


def test_get_redirected_link_sends_link_as_query_param():
    client = _client_with_mock_session()
    response = MagicMock()
    response.json.return_value = {"data": {"link": "https://direct"}}
    client.session.request.return_value = response

    link = client.get_redirected_link("https://alldebrid.com/link")

    _, kwargs = client.session.request.call_args
    assert kwargs["params"] == {"link": "https://alldebrid.com/link"}
    assert kwargs["json"] is None
    assert link == "https://direct"


def test_delete_torrent_sends_id_as_query_param():
    client = _client_with_mock_session()
    response = MagicMock()
    response.json.return_value = {"status": "success"}
    client.session.request.return_value = response

    client.delete_torrent("magnet-1")

    _, kwargs = client.session.request.call_args
    assert kwargs["params"] == {"id": "magnet-1"}
    assert kwargs["json"] is None
