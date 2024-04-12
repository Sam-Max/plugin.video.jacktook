
# Jacktook

A Kodi addon for torrent finding and streaming. 

## Requirements.

- Kodi 19+

## Features.

Torrent Search:
- Jackett 
- Prowlarr 
- Jacktook Burst
- Torrentio 
- Elhosted 

Torrent Engines:
- Jacktorr
- Torrest
- Elementum
- Real Debrid 
- Premiumize 

Metadata:
- TMDB  
- AniList, Simkl
- Fanart.tv
- TMDB helper

Others:
- API calls caching


## Installation of this addon (Jacktook)

The recommended way of installing the addon is through its [repository](https://github.com/Sam-Max/repository.jacktook), so that any updates will be automatically installed.

You can also install the addon without installing its repository. To do so, get the [latest release](https://github.com/Sam-Max/plugin.video.jacktook/releases/download/v0.1.4/plugin.video.jacktook-0.2.4.zip) from github. Please note that,  if there are any additional dependencies, they won't be resolved unless the repository is installed.

## Steps.

1. Install this addon (recommended way of installing the addon is through its repository)

2. Add configuration on addon settings to connect with Jackett, Prowlarr or Jacktook Burst (optional if using Torrentio or Elfhosted)

3. Install either [Jacktorr](https://github.com/Sam-Max/plugin.video.jacktorr), [Torrest](https://github.com/i96751414/plugin.video.torrest) or [Elementum](https://elementumorg.github.io/) addons.


**Notes**:
1. Jacktorr/Torrest/Elementum are optional if using Debrid services (Real Debrid or Premiumize)
2. Prowlarr IndexerIds field is comma separated trackers ids without space. Ex. 12,13,14. (from version 0.1.5)
3. When using Jackett or Prowlarr: select only a few trackers (3-4 max), avoid trackers with cloudflare protection (unless you configure FlareSolverr), and select if available on trackers options to retrieve magnets as priority and not torrent files, to improve search speed and results.
4. You can deploy/install on a remote server (instructions more below) the TorrServer Engine (torrent client that uses Jacktorr Addon). After that, you need to configure Jacktorr Addon with the TorrServer Engine IP/Domain and Port.
5. You can deploy/install on a remote server (instructions more below) the Torrest Engine (torrent client that uses Torrest Addon). After that, you need to configure Torrest Addon with the Torrest Engine IP/Domain and Port.
5. To use TMDB Helper Addon use: [jacktook.select.json](https://raw.githubusercontent.com/Sam-Max/plugin.video.jacktook/master/jacktook.select.json)

## How to run Jackett service using Docker:

Detailed instructions are available at [LinuxServer.io Jackett Docker](https://hub.docker.com/r/linuxserver/jackett/) 

## How to run Prowlarr service using Docker:

Detailed instructions are available at [Prowlarr Website](https://prowlarr.com/#downloads-v3-docker) 

## How to use Jacktook Burst:

See [Jacktook Burst](https://github.com/Sam-Max/script.jacktook.burst) 


## How to run Jacktorr Engine using Docker Compose (optional):

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

## Donations

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/sammax09)

-----

## Disclaimer:

This addon doesn't get sources by itself on torrent websites for legal reason and it should only be used to access movies and TV shows not protected by copyright.
