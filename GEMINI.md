# Gemini Code Assistant Report

## Project Overview

"Jacktook" is a Kodi addon meta-scraper designed for finding and streaming torrents. It acts as an aggregator, pulling content from various sources such as Stremio addons, Jackett, Prowlarr, and Telegram channels. It supports multiple torrent engines like Jacktorr, Torrest, and Elementum, and integrates seamlessly with Debrid services (RealDebrid, AllDebrid, Torbox, Premiumize). The addon enriches content with metadata from TMDB, MDBList, Trakt, and Fanart.tv.

The codebase is written in Python and targets Kodi version 20 (Nexus) and above.

## Project Structure

The project follows a standard Kodi addon structure with a focus on modularity.

### Repository Tree

```text
.
├── addon.xml
├── CHANGELOG.md
├── fanart.png
├── GEMINI.md
├── .gitignore
├── icon.png
├── jacktook.py
├── jacktook.select.json
├── jacktook.select.zip
├── LICENSE
├── README.md
├── service.py
├── lib
│   ├── api
│   │   ├── debrid
│   │   │   ├── alldebrid.py
│   │   │   ├── base.py
│   │   │   ├── debrider.py
│   │   │   ├── easydebrid.py
│   │   │   ├── premiumize.py
│   │   │   ├── realdebrid.py
│   │   │   └── torbox.py
│   │   ├── fanart
│   │   │   └── fanart.py
│   │   ├── jacktorr
│   │   │   └── jacktorr.py
│   │   ├── mdblist
│   │   │   └── mdblist.py
│   │   ├── plex
│   │   │   ├── models
│   │   │   │   └── plex_models.py
│   │   │   ├── __init__.py
│   │   │   ├── media_server.py
│   │   │   ├── plex.py
│   │   │   ├── settings.py
│   │   │   └── utils.py
│   │   ├── stremio
│   │   │   ├── addon_manager.py
│   │   │   ├── api_client.py
│   │   │   ├── __init__.py
│   │   │   └── models.py
│   │   ├── tmdbv3api
│   │   │   ├── objs
│   │   │   │   └── ... (TMDB models)
│   │   │   ├── as_obj.py
│   │   │   ├── exceptions.py
│   │   │   ├── __init__.py
│   │   │   ├── tmdb.py
│   │   │   └── utils.py
│   │   ├── trakt
│   │   │   ├── base_cache.py
│   │   │   ├── lists_cache.py
│   │   │   ├── main_cache.py
│   │   │   ├── trakt_cache.py
│   │   │   ├── trakt.py
│   │   │   └── trakt_utils.py
│   │   ├── tvdbapi
│   │   │   ├── __init__.py
│   │   │   └── tvdbapi.py
│   │   ├── webdav
│   │   │   └── webdav.py
│   │   └── __init__.py
│   ├── clients
│   │   ├── debrid
│   │   │   └── ...
│   │   ├── jackgram
│   │   │   ├── client.py
│   │   │   └── utils.py
│   │   ├── mdblist
│   │   │   └── mdblist.py
│   │   ├── stremio
│   │   │   └── ...
│   │   ├── subtitle
│   │   │   ├── deepl.py
│   │   │   ├── opensubstremio.py
│   │   │   ├── submanager.py
│   │   │   └── utils.py
│   │   ├── tmdb
│   │   │   ├── utils
│   │   │   ├── anime.py
│   │   │   ├── base.py
│   │   │   ├── collections.py
│   │   │   ├── people_client.py
│   │   │   └── tmdb.py
│   │   ├── trakt
│   │   │   ├── paginator.py
│   │   │   ├── trakt.py
│   │   │   └── utils.py
│   │   ├── webdav
│   │   │   └── client.py
│   │   ├── anilist.py
│   │   ├── anizip.py
│   │   ├── base.py
│   │   ├── elfhosted.py
│   │   ├── fma.py
│   │   ├── jackett.py
│   │   ├── medifusion.py
│   │   ├── peerflix.py
│   │   ├── plex.py
│   │   ├── prowlarr.py
│   │   ├── simkl.py
│   │   ├── torrentio.py
│   │   └── zilean.py
│   ├── db
│   │   ├── anime.py
│   │   ├── cached.py
│   │   └── pickle_db.py
│   ├── domain
│   │   └── torrent.py
│   ├── gui
│   │   ├── base_window.py
│   │   ├── custom_dialogs.py
│   │   ├── custom_progress.py
│   │   ├── filter_items_window.py
│   │   ├── filter_type_window.py
│   │   ├── play_next_window.py
│   │   ├── play_window.py
│   │   ├── qr_progress_dialog.py
│   │   ├── resolver_window.py
│   │   ├── resume_window.py
│   │   ├── source_pack_select.py
│   │   ├── source_pack_window.py
│   │   └── source_select.py
│   ├── jacktook
│   │   ├── client.py
│   │   ├── __init__.py
│   │   ├── listener.py
│   │   ├── provider_base.py
│   │   ├── providers.py
│   │   └── utils.py
│   ├── services
│   │   ├── preloader.py
│   │   └── trakt_sync.py
│   ├── utils
│   │   ├── clients
│   │   ├── debrid
│   │   ├── general
│   │   ├── kodi
│   │   ├── localization
│   │   ├── parsers
│   │   ├── player
│   │   ├── plex
│   │   ├── stremio
│   │   ├── torrent
│   │   ├── torrentio
│   │   └── views
│   ├── vendor
│   │   ├── bencodepy
│   │   ├── segno
│   │   └── torf
│   ├── actions.py
│   ├── downloader.py
│   ├── __init__.py
│   ├── navigation.py
│   ├── player.py
│   ├── router.py
│   ├── search.py
│   └── updater.py
├── resources
│   ├── img
│   │   ├── anime.png
│   │   ├── clear.png
│   │   ├── cloud2.png
│   │   ├── cloud.png
│   │   ├── donate.png
│   │   ├── download2.png
│   │   ├── download.png
│   │   ├── genre.png
│   │   ├── history.png
│   │   ├── lang.png
│   │   ├── magnet2.png
│   │   ├── magnet.png
│   │   ├── mdblist.png
│   │   ├── movies.png
│   │   ├── nextpage.png
│   │   ├── search.png
│   │   ├── settings.png
│   │   ├── status.png
│   │   ├── telegram.png
│   │   ├── tmdb.png
│   │   ├── torrentio.png
│   │   ├── trakt.png
│   │   ├── trending.png
│   │   └── tv.png
│   ├── language
│   │   ├── English
│   │   │   └── strings.po
│   │   ├── Portuguese
│   │   │   └── strings.po
│   │   ├── Portuguese (Brazil)
│   │   │   └── strings.po
│   │   └── Spanish
│   │       └── strings.po
│   ├── screenshots
│   │   ├── home.png
│   │   ├── settings.png
│   │   └── tv.png
│   ├── skins
│   │   └── Default
│   │       ├── 1080i
│   │       │   ├── customdialog.xml
│   │       │   ├── custom_progress_dialog.xml
│   │       │   ├── filter_items.xml
│   │       │   ├── filter_type.xml
│   │       │   ├── playing_next.xml
│   │       │   ├── qr_dialog.xml
│   │       │   ├── resolver.xml
│   │       │   ├── resume_dialog.xml
│   │       │   ├── source_pack_select.xml
│   │       │   ├── source_select_direct.xml
│   │       │   └── source_select.xml
│   │       └── media
│   ├── __init__.py
│   └── settings.xml
└── scripts
    ├── check_py37_compat.py
    └── manage_labels.py
```

### Core Components (`lib/`)

The `lib/` directory contains the addon's business logic, organized by function:

-   `api/`: Interfaces for external metadata providers (TMDB, Trakt, Fanart.tv).
-   `clients/`: Scraper clients for different sources (Jackett, Prowlarr, Stremio, etc.).
-   `db/`: Database interaction layer for caching and local storage.
-   `domain/`: Domain models and core logic.
-   `gui/`: UI rendering modules, handling Kodi's list items and dialogs.
-   `services/`: Logic for background tasks run by `service.py`.
-   `utils/`: General utility functions and helpers.
-   `vendor/`: Third-party libraries bundled with the addon.
-   `router.py`: The central routing mechanism that maps Kodi URL requests to specific actions.
-   `player.py`: Custom player logic for handling playback initiation and monitoring.

### Root Files

-   `addon.xml`: The addon manifest defining metadata, version, and dependencies.
-   `jacktook.py`: The main entry point for user interactions (GUI). It initializes the `router`.
-   `service.py`: The entry point for the background service. Handles periodic tasks like updates and library sync.

### Resources (`resources/`)

-   `settings.xml`: Defines the configuration options available in the addon settings menu.
-   `language/`: Localization files for multi-language support.
-   `images/`: Icons and artwork assets.

## Key Features

### Search & Scraping
-   **Aggregated Search**: Combines results from multiple providers into a single list.
-   **Smart Filtering**: Filters results by resolution, file size, and source type (cached/uncached).

### Playback Engines
-   **Native Debrid**: Direct streaming via RealDebrid, AllDebrid, or Premiumize.
-   **P2P Options**: Support for local torrent engines:
    -   **Jacktorr**: Wrapper for TorrServer.
    -   **Torrest**: Lightweight C++ client.
    -   **Elementum**: Integrated Kodi torrent client.

## Development Workflow

### Setup
1.  Clone the repository.
2.  Link the `plugin.video.jacktook` directory to your Kodi `addons` folder (or copy it).
3.  Restart Kodi to load the addon.

### Guidelines
-   **Compatibility**: Ensure code is compatible with Python 3.7+ (Kodi's minimum requirement). 
-   **Commits**: Strictly follow **Conventional Commits** format and a detailed body explaining *why* the change was made and *what* was changed.
    -   `fix(scraper): fix parsing for specialized trackers`
    -   `feat(ui): add new sort option for search results`
    -   `refactor(core): optimize router logic`
-   **Linting**: Keep code clean and follow PEP 8 where possible.

### Testing
-   A `pytest` infrastructure is in place for core utilities and pure logic.
-   Testing of Kodi-dependent code requires mocking (setup in `tests/conftest.py`).
-   Manual verification is still required for UI and Kodi-specific integrations.

### How to Run Tests
1.  **Install dependencies**:
    ```bash
    pip install -r requirements-test.txt
    ```
2.  **Run all tests**:
    ```bash
    pytest
    ```
3.  **Run with coverage**:
    ```bash
    pytest --cov=lib
    ```