
## 0.15.1
- HOTFIXED: Resolved multiple issues preventing addon updates.
- Ensured ordered results in show and episode listings.

## 0.15.0
- Delay closing resolve source window until playback starts.
- Added context menu options for selecting stremio sources and opening addon settings. 
- Added option on settings to clear all history
- Updated several menu icons for better consistency.
- Improved tvshow and movie metadata handling.
- Improved cast/crew extraction.
- Improved display and sorting of last files and titles.
- Other minor improvements and fixes.

Note: 
Si disfrutas de este addon, por favor considera apoyar el proyecto con una donación. Tus contribuciones ayudan a seguir mejorándolo y manteniéndolo. ¡Gracias!

If you enjoy this addon, please consider supporting the project with a donation. Your contributions helps keep improving and maintaining it. Thank you!

## 0.14.0
- Updated menu icons for Telegram and Downloads.
- Added filtering options setting for quality/source.
- Improved initialization and handling of invalid tokens on Real Debrid
- Simplified addon display name in jacktook.select.json.
- Other minor improvements.

Note: 
Si disfrutas de este addon, por favor considera apoyar el proyecto con una donación. Tus contribuciones ayudan a seguir mejorándolo y manteniéndolo. ¡Gracias!

If you enjoy this addon, please consider supporting the project with a donation. Your contributions helps keep improving and maintaining it. Thank you!

## 0.13.0 
- Added support for [MDBList](https://mdblist.com/)
- Added people category for movies and TV shows.
- Added context menu option to search people for movies and TV shows.
- Added setting to include/exclude TV show specials.
- Added metadata info to playback info for richer UI display.
- Added subtitle download option from the source select window.
- Added pagination to “last titles” view.
- Added export Kodi logs to paste.kodi.tv.
- Added excluded addons filter to Stremio toggle dialog to show only functional and manually tested addons.
- Other minor improvements and fixes.

Spanish:
- Se añadió soporte para [MDBList](https://mdblist.com/)
- Se añadió la categoría de personas para películas y series de TV.
- Se añadió una opción en el menú contextual para buscar personas en películas y series de TV.
- Se añadió la opción para incluir/excluir episodios especiales de series de TV.
- Se añadió información de metadatos en la información de reproducción para una interfaz más completa.
- Se añadió la opción de descarga de subtítulos desde la ventana de selección de fuente.
- Se añadió paginación a la vista de “últimos títulos”.
- Se añadió la exportación de registros de Kodi a paste.kodi.tv.
- Se añadió un filtro interno de addons excluidos al cuadro de diálogo de seleccion de addons de Stremio para mostrar solo addons funcionales y testeados.
- Otras mejoras y correcciones menores.

Note: 
Si disfrutas de este addon, por favor considera apoyar el proyecto con una donación. Tus contribuciones ayudan a seguir mejorándolo y manteniéndolo. ¡Gracias!

If you enjoy this addon, please consider supporting the project with a donation. Your contributions helps keep improving and maintaining it. Thank you!

## 0.12.0 
- Added TMDB collections, languages, networks, and popular filters. 
- Added QR code dialog to simplify authentication for debrid services
- Updated Stremio community addons URL to stable version (https://stremio-addons.net/).
- Added notification messages to users when no stremio addons or catalogs are selected.
- Added plugin categories for clearer window identification
- Other minor improvements and fixes.

Spanish:
- Se añadieron colecciones, idiomas, cadenas de televisión y filtros populares de TMDB.
- Se añadió un diálogo de código QR para simplificar la autenticación de los servicios de debrid.
- Se actualizó la URL de los addons de la comunidad de Stremio a la version estable (https://stremio-addons.net/).
- Se añadieron mensajes de notificación a los usuarios cuando no se seleccionan addons o catálogos de Stremio.
- Se añadieron categorías para una identificación más clara de las ventanas.
- Otras mejoras y correcciones menores.

Note: 
Si disfrutas de este addon, por favor considera apoyar el proyecto con una donación. Tus contribuciones ayudan a seguir mejorándolo y manteniéndolo. ¡Gracias!

If you enjoy this addon, please consider supporting the project with a donation. Your contributions helps keep improving and maintaining it. Thank you!

## 0.11.0 
- Added support for Debrider (https://debrider.app/)
- Other minor improvements and fixes.

## 0.10.0
- Added external cached search support for Real-Debrid.
- Updated URL for fetching community addons (migrated to beta.stremio-addons.net).
- Added resumable downloads and active download status.
- Added option for size range filtering.
- Added option to view Kodi logs and Kodi old logs.
- Added option to adjust number of threads.
- Improved Stremio catalog fetching to shows more catalogs.
- Other minor improvements and fixes.

Spanish: 
- Se añadió compatibilidad con búsqueda externa en caché para Real-Debrid.
- Se actualizó la URL para obtener addons de la comunidad (migracion a beta.stremio-addons.net).
- Se añadieron descargas reanudables y estado de descarga activa.
- Se añadió la opción de filtrado por rango de tamaño.
- Se añadió la opción de ver los registros de Kodi y los registros antiguos de Kodi.
- Se añadió la opción de ajustar el número de hilos.
- Se mejoró la obtención de catálogos de Stremio para mostrar más catálogos.
- Otras mejoras y correcciones menores.

Note: 
Si disfrutas de este addon, por favor considera apoyar el proyecto con una donación. Tus contribuciones ayudan a seguir mejorándolo y manteniéndolo. ¡Gracias!

If you enjoy this addon, please consider supporting the project with a donation. Your contributions helps keep improving and maintaining it. Thank you!

## 0.9.0
- Added Torrentio providers selection and settings UI. 
- Episodes are now marked as playable in TMDB and calendar views. 
- Replaced hardcoded context menu labels with translation entries (English and Spanish).
- Replaced hardcoded menus labels with translation entries. (English and Spanish).

Note: 
Si disfrutas de este addon, por favor considera apoyar el proyecto con una donación. Tus contribuciones ayudan a seguir mejorándolo y manteniéndolo. ¡Gracias!

If you enjoy this addon, please consider supporting the project with a donation. Your contributions helps keep improving and maintaining it. Thank you!

## 0.8.0
Features:
- Implement TV calendar on History and TV Shows menus, to show weekly episodes.
- Add context menu items for TMDB recommendations and similar content.
- Add installation prompts for missing addons: Elementum, Jacktorr, and Torrest. 
- Update filter options label to indicate usage of the left key.
- Adjust thread pool max workers calculation for better performance on low end devices.
Refactors:
- Replace usage of main_db with PickleDatabase across the addon. 
Fixes:
- Handle empty Stremio addons to prevent crashes. 
- Make Cache class thread-safe and more robust. 

## 0.7.0
- Add audio language selection for playback.
- Add functionality to add custom Stremio addons via URL.
- Add support for searching and filtering season packs (Jackett & Prowlarr).
- Add 'Show Changelog' setting and functionality to display addon updates.
- Renamed history menu items for clarity.
- Enabled scrolling for the title label in source selection.
- Implement token validation and adjust expiration time for Trakt authentication.
- Enhance subtitle file naming and slugify paths for better organization.
- Other minor improvements and fixes.

## 0.6.0
- Improve source select layout with clickable quality header. 
- Add more filtering options on source select window (languages, sources)
- Minor improvements and fixes

## 0.5.4
- HOTFIX: Fix Burst client not working.

## 0.5.3
- Added support to downloasd subtitles using Stremio OpenSubtitle addon.
- Added support for subtitle translation using DeepL (AI translation).
- Added auto-play with quality selection.
- Added auto-subtitle activation and selection on playback.

## 0.5.2
- Added download functionality
- Added Trakt scrobbling
- Added new menu item to add to Trakt watchlist.
- Added new menu item to mark as watched/unwatched on Trakt.
- Added new window to filter fetched results (right arrow or button to show).
- Many other improvements.

## 0.5.1
- UI Improvements 
- TMDB Helper json updated
- Some fixes and improvements

## 0.5.0
- Add support to import and use Stremio catalogs.
- Add setting button action to update Stremio addons after logged in.
- Some fixes and improvements with with Real Debrid packs detection.

## 0.4.10
* Hotfix: not detecting season pack when using debrid

## 0.4.9
* Add Priority Language selection setting to filter results.
* Fix missing some supported Stremio Addons.
* Fix autoplay

## 0.4.8
* Add support to import Stremio Addons from Stremio.io Account.

## 0.4.7
* Add Peerflix indexer support.
* Fix Mediafusion not playing sources when using torrents
* Other minor improvements and fixes

## 0.4.6
* Fix a bug that was causing fanart media details not been updating correctly

## 0.4.5
* Add language and region selection setting for TMDB.
* Fix RealDebrid episode selection on season packs
* Fix and handle torrents where its url redirects to magnets.
* Refactor settings.xml to new Kodi format.
* Other minor improvements and fixes

## 0.4.4
* some fixes and improvements

## 0.4.3
* Add search capability across multiple indexers
* Add filter by episode and season option 
* Some visual improvements for Arctic Horizon 2 skin.
* Other minor improvements and fixes

## 0.4.2
* Add Telegram menu (with option to enable/disable) with submenus to access Jackgram cached files (for advanced users)
* Add Anime year and genre search.
* Add TMDB year search for TV and Movies.
* Add Trakt popular lists.
* Some visual improvements on direct search source selection.
* Others minor improvements and fixes.

## 0.4.1
* Add play next dialog for episodes playback
* Add automatic playlist creation for shows episodes.
* Update tmdb helper to work with the new routing system.
* Update Jackgram Indexer.
* Others minor improvements and fixes.

## 0.4.0
* Add custom source select and resolve windows dialog.
* Improvements and fixes.

## 0.3.9
* Add EasyDebrid support.
* Add MediaFusion indexer.

## 0.3.8
* Real Debrid Improvements.
    - check if the torrent is on user torrents list, so not to add again.
    - add a check for max activate downloads, and delete one if limit achieved.
* Direct Search Improvements.
    - save search queries, and added menu item option to modify search queries by the user
* Torbox Improvements
    - use public ip address of user for torbox cdn selecction
* Multi Debrid Search support
* Add jackgram_results_per_page setting option for Jackgram client.

## 0.3.7
* Update Premiumize.
* Update Zilean (now supports movies and tv search)
* Update TMDB Helper json file with zip file

## 0.3.6
* Fix tmdb movies results not showing on main search
* Improve Jackett/Prowlarr integration with Debrid for faster results
* Add mechanism to detect indexers change when making a search
* Minor fixes and improvements.

## 0.3.5
* Fix Real Debrid Authentification not working
* Add Real Debrid remove authorization button and username info on settings
* Add option to select Kodi language for TMDB metadata.
* Playback improvements

## 0.3.4
* Improvements on Torbox

## 0.3.3
* Refactor Real Debrid due to recent API changes
* Fixed Torrentio not getting results
* Improvements on Torbox
* Other minor improvements and fixes

## 0.3.2
* Switch to tmdb and trakt for Anime section
* Add Jackgram Support
* Remove Plex Support 
* Bug fixes and improvements

## 0.3.1
* Add "rescrape item" context menu item to anime shows results
* Several bug fixes and some improvements

## 0.3.0
* Add Trakt support with several categories
* Update on genres menu and zilean indexer

## 0.2.9
* Add Zilean indexer support
* Minor bug fixes

## 0.2.8
* Add resume playback for videos
* Add new icons for main menu

## 0.2.7
* add "check if pack" context menu item
* several fixes and improvements

## 0.2.6
* Added service for auto-update addon 
* Added update addon setting action
* Whole refactoring of jacktook repository

## 0.2.5
* Added Plex support (beta)
* Added support for torbox debrid
* Major anime improvements
* Faster debrid fetch

## 0.2.4 (2024-04-12)
* Added jacktorr burst support
* Improvements on torrent fetch (faster resolve)
* Other minor improvements and fixes

## 0.2.3 (2024-04-06)
* Added jacktorr torrent client support
* Added jacktorr managment from addon instead of torrest
* Other minor improvements and fixes

## 0.2.2 (2024-03-22)
* Added autoplay feature
* Added clients timeouts and cache activation settings
* Added new Tmdb helper addon json
* Torrentio language improvements
* Fixed kodi 19 compatibility
* Other minor improvements and fixes

## 0.2.1 (2024-03-12)
* torrentio improvements (priority language, sort by language, etc)
* added portugese translation
* added trakt scrobbling support
* others improvements and fixes

## 0.2.0 (2024-03-04)
* Add option to select and use all torrents clients at the same time.
* Add pagination to tmdb and anilist search
* Fix for real debrid download history issue (only played videos will be saved)

## 0.1.9 (2024-02-21)
 * Fixed RD torrent stored on cloud
 * Add sort by quality to torrentio and elfhosted

## 0.1.8 (2024-02-21)
 * Add TMDB helper Addon support
 * Add new torrents menu
 * Add Elementum as another torrent client

## 0.1.7 (2024-02-21)
 * Add anime episode search
 * Add Premiumize support
 * Add Elfhosted support

## 0.1.6 (2024-02-12)
    * Fix a critical bug for Prowlarr

## 0.1.5 (2024-02-12)
    * Improvements for Prowlarr
    * Some UI changes

## 0.1.4 (2024-02-10)
    * Add Torrentio support

## 0.1.3 (2024-02-7)
    * Add "clear all cache" option on addon settings
    * Caching of indexers results
    * Improvements and fixes

## 0.1.2 (2024-02-5)

### Features

    * Add download uncached magnet to debrid option menu
    * Add show uncached option
    * Switch to torznab api for Jackett

## 0.1.1 (2024-01-30)

### Features

    * Add authentifcation flow for Realdebrid from Kodi
    
    * Fix and Update Debrid with Prowlarr Integration

    * Add new title history menu

    * Improvements on tmdb search

## 0.1.0 (2024-01-27)

### Features

    *  Real Debrid Support

    *  Improvements on tv search results

## 0.0.1 (2023-09-02)

### Features

    *  Jackett integration

    *  Torrest Integration

    *  TMDB Integration



