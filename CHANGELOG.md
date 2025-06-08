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



