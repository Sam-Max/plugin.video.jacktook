import json
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse
from unittest.mock import MagicMock, patch

from lib.clients.tmdb.people_client import PeopleClient
from lib.clients.tmdb.tmdb import TmdbClient
from lib.clients.tmdb.utils.utils import add_tmdb_movie_context_menu


def _parse_container_update_command(command):
    url = command[len("Container.Update(") : -1]
    query = parse_qs(urlparse(url).query)
    return {key: values[0] for key, values in query.items()}


def _get_menu_item(menu, label):
    for item_label, command in menu:
        if item_label == label:
            return item_label, command
    return None


def test_movie_multi_context_menu_passes_media_type_to_context_actions():
    with patch(
        "lib.clients.tmdb.utils.utils.translation",
        side_effect=lambda value: f"t-{value}",
    ):
        menu = add_tmdb_movie_context_menu(
            mode="multi",
            media_type="movie",
            title="Demo Movie",
            ids={"tmdb_id": 550},
        )

    recommendations = _get_menu_item(menu, "t-90050")
    similar = _get_menu_item(menu, "t-90051")
    people = _get_menu_item(menu, "t-90081")

    assert recommendations is not None
    assert similar is not None
    assert people is not None

    recommendations_query = _parse_container_update_command(recommendations[1])
    similar_query = _parse_container_update_command(similar[1])
    people_query = _parse_container_update_command(people[1])

    assert recommendations_query["action"] == "search_tmdb_recommendations"
    assert recommendations_query["mode"] == "multi"
    assert recommendations_query["media_type"] == "movie"

    assert similar_query["action"] == "search_tmdb_similar"
    assert similar_query["mode"] == "multi"
    assert similar_query["media_type"] == "movie"

    assert people_query["action"] == "search_people_by_id"
    assert people_query["mode"] == "multi"
    assert people_query["media_type"] == "movie"


def test_search_tmdb_recommendations_uses_movie_endpoint_for_multi_movie():
    results = SimpleNamespace(total_results=1, total_pages=2, results=[SimpleNamespace(id=11, title="R")])

    with patch("lib.clients.tmdb.tmdb.tmdb_get", return_value=results) as tmdb_get, patch(
        "lib.clients.tmdb.tmdb.set_content_type"
    ) as set_content_type, patch(
        "lib.clients.tmdb.tmdb.set_pluging_category"
    ), patch("lib.clients.tmdb.tmdb.make_list_item", return_value=MagicMock()), patch(
        "lib.clients.tmdb.tmdb.set_media_infoTag"
    ), patch(
        "lib.clients.tmdb.tmdb.BaseTmdbClient.add_media_directory_item",
        return_value=("url", MagicMock(), False),
    ), patch("lib.clients.tmdb.tmdb.add_directory_items_batch"), patch(
        "lib.clients.tmdb.tmdb.add_next_button"
    ) as add_next_button, patch("lib.clients.tmdb.tmdb.end_of_directory"), patch(
        "lib.clients.tmdb.tmdb.TmdbClient._get_cached_tmdb_item_metadata",
        return_value={},
    ), patch("lib.clients.tmdb.tmdb._apply_tmdb_view") as apply_view:
        TmdbClient.search_tmdb_recommendations(
            {
                "ids": json.dumps({"tmdb_id": 550}),
                "mode": "multi",
                "media_type": "movie",
                "page": "1",
            }
        )

    assert tmdb_get.call_args[0][0] == "movie_recommendations"
    set_content_type.assert_called_once_with("movies")
    apply_view.assert_called_once_with("movies")
    assert add_next_button.call_args.kwargs["media_type"] == "movie"


def test_search_tmdb_similar_uses_movie_endpoint_for_multi_movie():
    results = SimpleNamespace(total_results=1, total_pages=2, results=[SimpleNamespace(id=22, title="S")])

    with patch("lib.clients.tmdb.tmdb.tmdb_get", return_value=results) as tmdb_get, patch(
        "lib.clients.tmdb.tmdb.set_content_type"
    ) as set_content_type, patch(
        "lib.clients.tmdb.tmdb.set_pluging_category"
    ), patch("lib.clients.tmdb.tmdb.make_list_item", return_value=MagicMock()), patch(
        "lib.clients.tmdb.tmdb.set_media_infoTag"
    ), patch(
        "lib.clients.tmdb.tmdb.BaseTmdbClient.add_media_directory_item",
        return_value=("url", MagicMock(), False),
    ), patch("lib.clients.tmdb.tmdb.add_directory_items_batch"), patch(
        "lib.clients.tmdb.tmdb.add_next_button"
    ) as add_next_button, patch("lib.clients.tmdb.tmdb.end_of_directory"), patch(
        "lib.clients.tmdb.tmdb.TmdbClient._get_cached_tmdb_item_metadata",
        return_value={},
    ), patch("lib.clients.tmdb.tmdb._apply_tmdb_view") as apply_view:
        TmdbClient.search_tmdb_similar(
            {
                "ids": json.dumps({"tmdb_id": 550}),
                "mode": "multi",
                "media_type": "movie",
                "page": "1",
            }
        )

    assert tmdb_get.call_args[0][0] == "movie_similar"
    set_content_type.assert_called_once_with("movies")
    apply_view.assert_called_once_with("movies")
    assert add_next_button.call_args.kwargs["media_type"] == "movie"


def test_search_people_by_id_uses_movie_credits_for_multi_movie():
    credits = SimpleNamespace(cast=[])

    with patch("lib.clients.tmdb.people_client.tmdb_get", return_value=credits) as tmdb_get, patch(
        "lib.clients.tmdb.people_client.set_content_type"
    ), patch("lib.clients.tmdb.people_client.set_pluging_category"), patch(
        "lib.clients.tmdb.people_client.execute_thread_pool"
    ), patch("lib.clients.tmdb.people_client.end_of_directory"):
        PeopleClient.search_people_by_id(
            {
                "mode": "multi",
                "media_type": "movie",
                "ids": json.dumps({"tmdb_id": 550}),
            }
        )

    assert tmdb_get.call_args[0][0] == "movie_credits"
    assert tmdb_get.call_args.kwargs["params"] == 550
