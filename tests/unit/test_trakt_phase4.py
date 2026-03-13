import datetime
from types import SimpleNamespace

from lib.api.trakt.trakt import TraktTV
from lib.clients.trakt.trakt import TraktPresentation


def test_build_up_next_entries_prefers_resume_progress_items():
    watched_shows = [
        {
            "show": {"title": "Show One", "ids": {"tmdb": 1}},
            "seasons": [{"number": 1, "episodes": [{"number": 1}]}],
        }
    ]
    progress_items = [
        {
            "show": {"title": "Show One", "ids": {"tmdb": 1}},
            "episode": {"season": 1, "number": 1, "title": "Pilot"},
            "progress": 42,
            "paused_at": "2026-03-13T18:00:00.000Z",
        }
    ]

    entries = TraktTV._build_up_next_entries(
        watched_shows,
        progress_items,
        fetcher=lambda *_args, **_kwargs: None,
        now_dt=datetime.datetime(2026, 3, 13),
    )

    assert len(entries) == 1
    assert entries[0]["type"] == "resume"
    assert entries[0]["episode"]["number"] == 1
    assert entries[0]["progress"] == 42


def test_build_up_next_entries_finds_next_aired_episode():
    watched_shows = [
        {
            "show": {"title": "Show Two", "ids": {"tmdb": 22}},
            "seasons": [
                {
                    "number": 1,
                    "episodes": [
                        {"number": 1, "last_watched_at": "2026-03-10T18:00:00.000Z"}
                    ],
                }
            ],
        }
    ]

    def fetcher(name, payload):
        if name == "tv_details":
            return SimpleNamespace(number_of_seasons=1)
        return SimpleNamespace(
            episodes=[
                SimpleNamespace(episode_number=1, name="Ep1", air_date="2026-03-01"),
                SimpleNamespace(episode_number=2, name="Ep2", air_date="2026-03-05"),
                SimpleNamespace(episode_number=3, name="Ep3", air_date="2026-03-20"),
            ]
        )

    entries = TraktTV._build_up_next_entries(
        watched_shows,
        [],
        fetcher=fetcher,
        now_dt=datetime.datetime(2026, 3, 13),
    )

    assert len(entries) == 1
    assert entries[0]["type"] == "next"
    assert entries[0]["episode"]["number"] == 2
    assert entries[0]["episode"]["title"] == "Ep2"


def test_format_account_info_includes_profile_and_stats():
    content = TraktPresentation._format_account_info(
        {
            "settings": {
                "user": {
                    "username": "demo_user",
                    "name": "Demo",
                    "joined_at": "2024-01-01T00:00:00.000Z",
                    "vip": True,
                },
                "account": {
                    "private": False,
                    "timezone": "Europe/Madrid",
                    "locale": "es",
                },
                "connections": {"google": True},
            },
            "stats": {
                "movies": {"watched": 12, "collected": 4},
                "shows": {"watched": 3, "collected": 1},
                "episodes": {"watched": 40},
                "lists": {"count": 2},
            },
        }
    )

    assert "demo_user" in content
    assert "Movies Watched: 12" in content
    assert "Episodes Watched: 40" in content
    assert "Timezone: Europe/Madrid" in content
