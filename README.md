
# Jacktook

A Kodi addon for torrent finding and streaming. 

## Features.

**Torrent Sources**: Stremio Addons, Jacktook Burst, Jackgram, Jackett, Prowlarr, Zilean.

**Torrent Engines**: Jacktorr, Torrest and Elementum.

**Telegram Engines**: Jackgram.

**Debrid Services**: RealDebrid, Premiumize, Torbox, EasyDebrid + Debrid Services configured with Stremio Addons.

**Metadata**: TMDB, Trakt and Fanart.tv. 

## Requirements.

- Kodi 20+

## Installation of this addon (Jacktook)

The recommended way of installing the addon is through its [repository](https://github.com/Sam-Max/repository.jacktook), so that any updates will be automatically installed.

**Note**:

- After each update, it is recommended that you clear cache to make sure changes takes effect.

- Optional install either [Jacktorr](https://github.com/Sam-Max/plugin.video.jacktorr), [Torrest](https://github.com/i96751414/plugin.video.torrest) or [Elementum](https://elementumorg.github.io/), for torrent p2p streaming.


**Notes**:
1. Jacktorr|Jackgram|Torrest|Elementum are optional if using Debrid.
2. When using Jackett or Prowlarr: select only a few trackers (3-4 max), avoid trackers with cloudflare protection (unless you configure FlareSolverr), and select if available on trackers options to retrieve magnets as priority and not torrent files, to get more results.
3. Prowlarr Indexers-Ids field is space separated ids of the indexers you have on your Prowlarr instance configured. Ex. 25 27 14. By default this field is empty, which means it will search on all your indexers.
4. You can install on a remote server the TorrServer Engine (torrent client that uses Jacktorr Addon) using Docker or you can also install the Android App. After that, you need to configure Jacktorr Addon with the TorrServer Engine IP/Domain and Port.
5. You can install on a remote server the Torrest Engine (torrent client that uses Torrest Addon). After that, you need to configure Torrest Addon with the Torrest Engine IP/Domain and Port.
5. To use TMDB Helper Addon use: [jacktook.select.json](https://raw.githubusercontent.com/Sam-Max/plugin.video.jacktook/master/jacktook.select.json)


## How to use Jacktook Burst:

Install addon to use it. [Jacktook Burst](https://github.com/Sam-Max/script.jacktook.burst) 

## How to run Jackett service using Docker:

Detailed instructions are available at [LinuxServer.io Jackett Docker](https://hub.docker.com/r/linuxserver/jackett/) 

## How to run Prowlarr service using Docker:

Detailed instructions are available at [Prowlarr Website](https://prowlarr.com/#downloads-v3-docker) 

## How to run self-hosted Zilean service using Docker:

Detailed instructions for self-hosting are available at [Zilean](https://github.com/iPromKnight/zilean) 


## How to run Jackgram service using Docker:

Detailed instructions are available at [Jackgram](https://github.com/sam-max/Jackgram) 

## How to run Jacktorr Torrent Engine on Android (optional):

Install the app from: [TorrServer](https://github.com/YouROK/TorrServer/releases) or from PlayStore.

## How to run Jacktorr Torrent Engine using Docker Compose (optional):

```
version: '3.3'
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
            - './CACHE:/opt/ts/torrents'
            - './CONFIG:/opt/ts/config'
        ports:
            - '5665:5665'
        restart: unless-stopped
```


## How to run Torrest Engine using Docker (optional):

1. Create a Dockerfile with the following content (make sure to check before the latest `VERSION` of the binary and your `OS` and `ARCH` and update accordingly).

```
FROM ubuntu:22.04

RUN apt-get update && apt-get install -y curl unzip

ARG VERSION=0.0.5 OS=linux ARCH=x64

RUN curl -L https://github.com/i96751414/torrest-cpp/releases/download/v${VERSION}/torrest.${VERSION}.${OS}_${ARCH}.zip -o torrest.zip \
    && unzip torrest.zip -d /usr/local/lib \
    && rm torrest.zip

RUN chmod +x /usr/local/lib/torrest

CMD ["/usr/local/lib/torrest", "--log-level", "INFO"]
```

2. Build the Dockerfile

    docker build -t torrest-cpp .

3. Run the container on port 8080 (default port).
    
    docker run -p 8080:8080 --name torrest-service torrest-cpp

## Screenshots:

![](https://raw.githubusercontent.com/Sam-Max/plugin.video.jacktook/master/resources/screenshots/settings.png)


## Disclaimer:

This addon doesn't get sources by itself on torrent websites for legal reason and it should only be used to access movies and TV shows not protected by copyright.
