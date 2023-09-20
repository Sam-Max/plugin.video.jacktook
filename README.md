
# Jacktook

A Kodi addon for torrent finding and streaming. 

The addon doesn't get sources by itself on torrent websites for legal reason and should only be used to access movies and TV shows not protected by copyright.

## Requirements.

- Kodi 19+

## Features.

- Jackett integration
- Prowlarr integration
- Torrest Integration
- TMDB Integration 
- AniList Integration
- Fanart.tv Integration
- API calls caching


## Steps.

1. Install Jackett. [Jackett](https://github.com/Jackett/Jackett) and/or [Prowlarr](https://github.com/Prowlarr/Prowlarr)

2. Install this addon.

3. Add configuration on addon settings to connect with Jackett and/or Prowlarr 

4. Install Torrest addon. [Torrest](https://github.com/i96751414/plugin.video.torrest)


**Note**:

You can deploy/install the [Torrest Service](https://github.com/i96751414/torrest-cpp)(torrent client that comes built-in on Torrest Addon that provides an API specially made for streaming), on a remote server (instructions more below). After that, you need to configure Torrest addon with the Torrest service IP/Domain and Port.


## Installation of this addon (Jacktook)

The recommended way of installing the addon is through its [repository](https://github.com/Sam-Max/repository.jacktook), so that any updates will be automatically installed.

You can also install the addon without installing its repository. To do so, get the [latest release](https://github.com/Sam-Max/plugin.video.jacktook/releases/download/v0.0.9/plugin.video.jacktook-0.0.9.zip) from github. Please note that, if there are any additional dependencies, they won't be resolved unless the repository is installed.

## How to run Jackett service using Docker:

Detailed instructions are available at [LinuxServer.io Jackett Docker](https://hub.docker.com/r/linuxserver/jackett/) 

## How to run Prowlarr service using Docker:

Detailed instructions are available at [Prowlarr Website](https://prowlarr.com/#downloads-v3-docker) 

## How to run Torrest service using Docker (optional):

1. Create a Dockerfile with the following content (make sure to check before the latest `VERSION` of the binary and your `OS` and `ARCH` and update accordingly).

```
FROM ubuntu:22.04

RUN apt-get update && apt-get install -y curl unzip

ARG VERSION=0.0.4 OS=linux ARCH=x64

RUN curl -L https://github.com/i96751414/torrest-cpp/releases/download/v${VERSION}/torrest.${VERSION}.${OS}_${ARCH}.zip -o torrest.zip \
    && unzip torrest.zip -d /usr/local/lib \
    && rm torrest.zip

RUN chmod +x /usr/local/lib/torrest

CMD ["/usr/local/lib/torrest"]
```

2. Build the Dockerfile

    docker build -t torrest-cpp .

3. Run the container on port 8080 (default port).
    
    docker run -p 8080:8080 torrest-cpp

## Screenshots:

![](https://raw.githubusercontent.com/Sam-Max/plugin.video.jacktook/master/resources/screenshots/settings.png)


