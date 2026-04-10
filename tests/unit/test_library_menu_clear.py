from lib.nav import library_history
from lib.utils.views import library


def test_library_menu_adds_clear_context_menu(monkeypatch):
    added = []
    end_calls = []

    class _ListItem:
        def __init__(self, label=""):
            self.label = label
            self.context_menu = []

        def addContextMenuItems(self, items):
            self.context_menu.extend(items)

    monkeypatch.setattr(library_history, "build_list_item", lambda name, icon: _ListItem(name))
    monkeypatch.setattr(
        library_history,
        "translation",
        lambda value: {90202: "My TvShows", 90203: "My Movies", 90201: "Library", 90021: "Upcoming Episodes", 90690: "Clear All Items"}.get(value, str(value)),
    )
    monkeypatch.setattr(library_history, "set_pluging_category", lambda *args, **kwargs: None)
    monkeypatch.setattr(library_history, "end_of_directory", lambda *args, **kwargs: end_calls.append(kwargs))
    monkeypatch.setattr(
        library_history,
        "container_update",
        lambda action, **params: "Container.Update(plugin://plugin.video.jacktook?action={}{})".format(
            action,
            "".join("&{}={}".format(key, value) for key, value in params.items()),
        ),
    )
    monkeypatch.setattr(library_history, "build_url", lambda action, **params: "plugin://plugin.video.jacktook?action={}{}".format(action, "".join("&{}={}".format(key, value) for key, value in params.items())))
    monkeypatch.setattr(
        library_history,
        "add_directory_items_batch",
        lambda items: added.extend(list_item for _url, list_item, _is_folder in items),
    )

    library_history.library_menu({})

    assert added[0].label == "My TvShows"
    assert added[1].label == "My Movies"
    assert added[0].context_menu == [("Clear All Items", "Container.Update(plugin://plugin.video.jacktook?action=library_shows&clear=1)")]
    assert added[1].context_menu == [("Clear All Items", "Container.Update(plugin://plugin.video.jacktook?action=library_movies&clear=1)")]
    assert end_calls == [{"cache": False}]


def test_maybe_clear_library_clears_requested_mode_when_confirmed(monkeypatch):
    cleared = []

    monkeypatch.setattr(library_history, "translation", lambda value: str(value))
    monkeypatch.setattr(library_history.Dialog, "yesno", lambda self, *args, **kwargs: True)
    monkeypatch.setattr(
        "lib.utils.views.library.clear_library_items",
        lambda params: cleared.append(params),
    )

    library_history._maybe_clear_library("tv", {"clear": 1})

    assert cleared == [{"mode": "tv"}]


def test_clear_library_items_removes_only_requested_mode(monkeypatch):
    database = {
        "Show 1": {"mode": "tv"},
        "Movie 1": {"mode": "movies"},
        "Movie 2": {"mode": "movie"},
    }

    monkeypatch.setattr(
        library.PickleDatabase,
        "get_key",
        lambda self, key: database,
    )
    monkeypatch.setattr(
        library.PickleDatabase,
        "delete_item",
        lambda self, key, subkey, commit=True: database.pop(subkey, None),
    )
    monkeypatch.setattr(
        library.PickleDatabase,
        "commit",
        lambda self: None,
    )
    deleted = []
    monkeypatch.setattr(library.cache, "delete", lambda key: deleted.append(key))
    monkeypatch.setattr(library, "notification", lambda *args, **kwargs: None)
    monkeypatch.setattr(library, "translation", lambda value: str(value))

    import xbmc

    monkeypatch.setattr(xbmc, "executebuiltin", lambda *args, **kwargs: None)

    removed = library.clear_library_items({"mode": "movies"})

    assert database == {"Show 1": {"mode": "tv"}}
    assert deleted == ["library_view|tv", "library_view|movies"]
    assert removed == 2
