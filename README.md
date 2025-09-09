# Jacktook

A Kodi addon for torrent finding and streaming.

---

## Features

- **Torrent Sources**:  
  Stremio Addons, Jacktook Burst, Jackgram, Jackett, Prowlarr, Zilean.

- **Torrent Engines**:  
  Jacktorr, Torrest, and Elementum.

- **Telegram Engines**:  
  Jackgram.

- **Debrid Services**:  
  Debrider, RealDebrid, Premiumize, Torbox, and Debrid Services configured with Stremio Addons.

- **Metadata**:  
  TMDB, MDBList, Trakt, Fanart.tv and Stremio catalogs.

- **Stremio Subtitle Download**:  
  Download subtitles directly from Stremio sources.

- **Deepl Integration**:  
  Translate subtitles using Deepl API.

---

## Requirements

- **Kodi Version**: 20+

---

## Installation

The recommended way to install the addon is through its [repository](https://github.com/Sam-Max/repository.jacktook), ensuring automatic updates.

### Notes:

- After each update, clear the cache to ensure changes take effect.
- Optional: Install one of the following for torrent P2P streaming:
  - [Jacktorr](https://github.com/Sam-Max/plugin.video.jacktorr)
  - [Torrest](https://github.com/i96751414/plugin.video.torrest)
  - [Elementum](https://elementumorg.github.io/)

---

## Usage Notes

1. **Optional Engines**:  
   Jacktorr, Jackgram, Torrest, and Elementum are optional if using Debrid services.

2. **Jackett or Prowlarr Configuration**:

   - Select only a few trackers (3-4 max).
   - Avoid trackers with Cloudflare protection unless configured with FlareSolverr.
   - Prioritize retrieving magnets over torrent files for better results.

3. **Prowlarr Indexers-Ids Field**:

   - Space-separated IDs of the indexers configured in your Prowlarr instance (e.g., `25 27 14`).
   - Leave empty to search all indexers.

4. **TorrServer Engine**:

   - Install on a remote server using Docker or the Android Apk.
   - Configure Jacktorr Addon with the TorrServer Engine's IP/Domain and Port.

5. **Torrest Engine**:

   - Install on a remote server using Docker or use the built-in Torrest Addon Engine.
   - Configure Torrest Addon with the Torrest Engine's IP/Domain and Port.

6. **TMDB Helper Addon**:  
   Use the following configuration file:  
   [jacktook.select.json](https://raw.githubusercontent.com/Sam-Max/plugin.video.jacktook/master/jacktook.select.json)

---

## Additional Guides

### Jacktook Burst

Install the addon: [Jacktook Burst](https://github.com/Sam-Max/script.jacktook.burst)

### Jackett Service (Docker)

Follow instructions at [LinuxServer.io Jackett Docker](https://hub.docker.com/r/linuxserver/jackett/)

### Prowlarr Service (Docker)

Follow instructions at [Prowlarr Website](https://prowlarr.com/#downloads-v3-docker)

### Zilean Service (Docker)

Follow instructions at [Zilean GitHub](https://github.com/iPromKnight/zilean)

### Jackgram Service (Docker)

Follow instructions at [Jackgram GitHub](https://github.com/sam-max/Jackgram)

## Deepl Integration

Jacktook supports subtitle and metadata translation using the Deepl API.

### How to Get a Deepl API Key

1. Go to the [Deepl API Signup Page](https://www.deepl.com/pro-api?cta=header-pro-api/).
2. Register for a free account (the "DeepL API Free" plan).
3. After registration, you will find your API authentication key in your Deepl account dashboard.

### Free Usage

- The Deepl API Free plan allows up to **500,000 characters per month** for translation at no cost.
- For higher limits, you can upgrade to a paid plan.

**Note:** Enter your Deepl API key in the Jacktook addon settings to enable translation features.

---

## Optional Torrent Engines

### Jacktorr on Android

Install the app: [TorrServer](https://github.com/YouROK/TorrServer/releases) or from the Play Store.

### Jacktorr using Docker Compose

```yaml
version: "3.3"
services:
  torrserver:
    image: ghcr.io/yourok/torrserver
    container_name: torrserver
    environment:
      - TS_PORT=5665
      - TS_DONTKILL=1
      - TS_HTTPAUTH=0
      - TS_CONF_PATH=/opt/ts/config
      - TS_TORR_DIR=/opt/ts/torrents
    volumes:
      - "./CACHE:/opt/ts/torrents"
      - "./CONFIG:/opt/ts/config"
    ports:
      - "5665:5665"
    restart: unless-stopped
```

### Torrest Engine using Docker

1. Create a `Dockerfile`:

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

2. Build the Docker image:

   ```bash
   docker build -t torrest-cpp .
   ```

3. Run the container:
   ```bash
   docker run -p 8080:8080 --name torrest-service torrest-cpp
   ```

---

## Screenshots

![Settings Screenshot](https://raw.githubusercontent.com/Sam-Max/plugin.video.jacktook/master/resources/screenshots/settings.png)

---

## Disclaimer

This addon does not scrape torrent websites for legal reasons. It should only be used to access movies and TV shows not protected by copyright.

---

