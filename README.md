<div align="center">

# 🚀 Jacktook

*An advanced meta-scraper and streaming Kodi addon for enthusiasts.*

[![Kodi Version](https://img.shields.io/badge/Kodi-20+-blue.svg)](https://kodi.tv)
[![License](https://img.shields.io/badge/License-GPL%20v3-green.svg)](LICENSE)
[![Support on Ko-fi](https://img.shields.io/badge/Support%20on%20Ko--fi-F16061?logo=ko-fi&logoColor=white)](https://ko-fi.com/sammax09)

---

[Features](#-features) • [Installation](#-installation) • [Configuration](#-configuration--usage) • [External Engines](#-external-engines-optional) • [Screenshots](#-screenshots)

</div>

## 🌟 Overview

**Jacktook** is a powerful Kodi addon designed to aggregate torrents and metadata from a vast array of sources. Whether you prefer P2P streaming, Stremio addons, or Debrid services, Jacktook provides a unified, streamlined interface for a seamless media discovery and playback experience.

---

## ✨ Features

### 🔍 Search & Scraping
- **Aggregated Sources**: Stremio Addons, Jacktook Burst, Jackgram, Jackett, Prowlarr. 
- **Rich Metadata**: Integration with TMDB, MDBList, Trakt, Fanart.tv, and Stremio catalogs.
- **Smart Filtering**: Advanced results filtering by quality, size, and source.

### 🧩 Stremio Ecosystem
- **Cloud Configuration**: Import and sync your entire configuration, including installed addons and Debrid tokens, directly from your Stremio account.
- **Catalog Navigation**: Browse and search Stremio's extensive metadata catalogs.
- **Stream Scraper**: Scraping and filtering of Stremio streams by resolution, file size, and quality.
- **Flexible Management**: Add new addons via URL, search for community addons, or toggle existing ones on/off on the fly.
- **Web Server Manager**: A powerful local web interface to manage your Stremio sources from your phone or PC. Scan a QR code in Kodi and start managing!

### 🎥 Playback & Engines
- **Direct Torrent Engines**: Integrated support for **Jacktorr**, **Torrest**, and **Elementum**.
- **Debrid Support**: Native support for RealDebrid, AllDebrid, Premiumize, and Torbox.
- **Telegram Streaming**: Stream directly from Telegram via Jackgram.

### 🛠️ Utilities
- **Automatic Subtitles**: Download subtitles directly from Stremio sources.
- **DeepL Translation**: Real-time translation of subtitles and metadata using the DeepL API.
- **TMDB Helper Integration**: Full compatibility with TMDB Helper via custom players.

---

## 📥 Installation

The recommended installation method is via the official repository to ensure you receive automatic updates.

1.  **Download the Repository**: [Sam-Max Repository](https://github.com/Sam-Max/repository.jacktook)
2.  **Install via Kodi**: `Add-ons > Install from zip file`
3.  **Install Jacktook**: `Add-ons > Install from repository > Sam-Max Repository > Video add-ons > Jacktook`

---

## ⚙️ Configuration & Usage

### 🚀 Stremio Integration
Jacktook can import configurations and Debrid services directly from your Stremio account.
- Enable Stremio in settings.
- Login to your Stremio account to sync your installed addons and Debrid tokens.

### 🔍 Jackett & Prowlarr
To optimize search performance:
- Select only 3–4 high-quality trackers.
- Avoid trackers behind Cloudflare unless you use **FlareSolverr**.
- For **Prowlarr**, you can specify Indexer IDs (space-separated) in the settings to target specific sources.

### 🌐 DeepL Integration
Translate subtitles and metadata instantly.
1. Get a free API key at [DeepL API](https://www.deepl.com/pro-api).
2. Enter the key in Jacktook settings.
3. Enjoy up to 500,000 characters of free translation per month.

### 🧩 TMDB Helper
For the best experience with TMDB Helper, use the following configuration file:
- [jacktook.select.json](https://raw.githubusercontent.com/Sam-Max/plugin.video.jacktook/master/jacktook.select.json)

---

## 🏗️ External Engines (Optional)

If you are not using Debrid services, you can use these engines for P2P streaming:

| Engine | Description | Platform |
| :--- | :--- | :--- |
| **Jacktorr** | Advanced TorrServer wrapper | Android / Docker |
| **Torrest** | Lightweight C++ BitTorrent engine | Linux / Docker |
| **Elementum** | Proven P2P streaming solution | All Kodi platforms |

### 🐳 Docker Setup Examples

#### TorrServer (Jacktorr)
```yaml
services:
  torrserver:
    image: ghcr.io/yourok/torrserver
    container_name: torrserver
    environment:
      - TS_PORT=5665
    ports:
      - "5665:5665"
    restart: unless-stopped
```

#### Torrest Engine
```dockerfile
FROM ubuntu:22.04
RUN apt-get update && apt-get install -y curl unzip
ARG VERSION=0.0.5 OS=linux ARCH=x64
RUN curl -L https://github.com/i96751414/torrest-cpp/releases/download/v${VERSION}/torrest.${VERSION}.${OS}_${ARCH}.zip -o torrest.zip \
    && unzip torrest.zip -d /usr/local/lib \
    && rm torrest.zip
RUN chmod +x /usr/local/lib/torrest
CMD ["/usr/local/lib/torrest", "--log-level", "INFO"]
```

---

## 📸 Screenshots

| Home Screen | TV Shows |
| :---: | :---: |
| ![Home](https://raw.githubusercontent.com/Sam-Max/plugin.video.jacktook/master/resources/screenshots/home.png) | ![TV](https://raw.githubusercontent.com/Sam-Max/plugin.video.jacktook/master/resources/screenshots/tv.png) |
| **Settings** | **Extras** |
| ![Settings](https://raw.githubusercontent.com/Sam-Max/plugin.video.jacktook/master/resources/screenshots/settings.png) | ![Extras](https://raw.githubusercontent.com/Sam-Max/plugin.video.jacktook/master/resources/screenshots/extras.png) |

---

## ☕ Support

If you enjoy using **Jacktook** and want to support its development, you can buy me a coffee! Your support helps keep the project active and enables future improvements.

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/sammax09)

---

## ⚖️ Disclaimer

This addon is a meta-search tool. It does not host or scrape torrent websites directly. Users are responsible for the content they access and should comply with local copyright laws.

---

## 🤝 Collaborators

A huge thanks to everyone who has contributed to this project:

<p align="left">
  <a href="https://github.com/addon-rajada"><img src="https://github.com/addon-rajada.png?size=50" width="50" height="50" alt="addon-rajada" title="addon-rajada"/></a>
  <a href="https://github.com/cleanhands"><img src="https://github.com/cleanhands.png?size=50" width="50" height="50" alt="cleanhands" title="cleanhands"/></a>
  <a href="https://github.com/coffelius"><img src="https://github.com/coffelius.png?size=50" width="50" height="50" alt="Gabriel Ortega" title="Gabriel Ortega"/></a>
  <a href="https://github.com/icarok99"><img src="https://github.com/icarok99.png?size=50" width="50" height="50" alt="Ícaro Maicon" title="Ícaro Maicon"/></a>
  <a href="https://github.com/asylumexp"><img src="https://github.com/asylumexp.png?size=50" width="50" height="50" alt="Sam Heinz" title="Sam Heinz"/></a>
  <a href="https://github.com/saucepanlid"><img src="https://github.com/saucepanlid.png?size=50" width="50" height="50" alt="saucepanlid" title="saucepanlid"/></a>
</p>

---

<div align="center">
Made with ❤️ for the Kodi Community
</div>
