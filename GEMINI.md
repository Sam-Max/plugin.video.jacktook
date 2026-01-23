# Gemini Code Assistant Report

## Project Overview

This project is a Kodi addon named "Jacktook" for finding and streaming torrents. It acts as a meta-scraper, aggregating content from various sources, including Stremio addons, Jackett, Prowlarr, and Telegram channels. It supports multiple torrent engines like Jacktorr, Torrest, and Elementum, and integrates with Debrid services such as RealDebrid, AllDebrid, and Premiumize. The addon also provides metadata from TMDB, MDBList, Trakt, and Fanart.tv.

The addon is written in Python and is designed for Kodi version 20 and above.

## Project Structure

The project is organized into the following main directories:

-   `lib/`: Contains the core logic of the addon, including clients for various services, database management, GUI elements, and utility functions.
-   `resources/`: Contains addon resources like settings definitions (`settings.xml`), language files, and images.
-   `service.py`: A background service that runs independently of the addon's UI. It handles tasks like checking for updates, managing downloads, and ensuring the correct Kodi version is being used.
-   `jacktook.py`: The main entry point for the addon's UI. It initializes the router that handles user actions.
-   `addon.xml`: The addon's metadata file, containing information like the addon's ID, version, and dependencies.

### Key Files and their Purpose

-   `jacktook.py`: The main entry point for the addon. It calls the `addon_router` to handle user actions.
-   `service.py`: The background service that handles tasks like update checks and database setup.
-   `lib/router.py`: The central hub of the addon's UI. It maps user actions to their corresponding functions.
-   `lib/actions.py`: Contains the logic for resolving and playing media.
-   `lib/clients/`: This directory contains modules for interacting with various external services like Jackett, Prowlarr, Trakt, and Debrid providers. Each file in this directory is a client for a specific service.
-   `resources/settings.xml`: Defines the addon's settings that can be configured by the user in the Kodi UI.

## Building and Running

This is a Kodi addon and is not intended to be run as a standalone application. To use this addon, you need to have Kodi installed. The recommended way to install the addon is through its repository, as mentioned in the `README.md` file.

### Development

For development purposes, you can manually install the addon in Kodi by copying the project directory to the Kodi addons directory. The location of the addons directory varies depending on your operating system.

### Testing

The project contains a `tests` directory, but it is not clear how to run the tests. There are no explicit test commands or configurations in the project files.

## Development Conventions

-   The addon follows the standard structure of a Kodi addon.
-   The code is written in Python and appears to be compatible with Python 3.
-   The addon uses a router to handle user actions, which is a common pattern in Kodi addons.
-   The addon makes extensive use of external services and APIs, with dedicated client modules for each service.
-   The addon uses a background service to perform tasks that do not require user interaction.
-   The addon uses XML files to define the addon's settings and GUI elements.
-   The project includes a `.gitignore` file, which lists files and directories that should be excluded from version control.
- Always use conventional commits message format with a detailed body explaining *why* the change was made and *what* was changed.