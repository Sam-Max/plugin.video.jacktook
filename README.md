
# Jackewlarr

A kodi addon that integrates Jackett and Prowlarr with Torrest. 

Inspired by [Haru Addon](https://github.com/pikdum/plugin.video.haru)

## Requirements.

- Kodi 19+

## Features.

- Jackett integration

- Prowlarr integration

- Torrest Integration

- TMDB Integration

## Steps.

1. Install Jackett. [Jackett](https://github.com/Jackett/Jackett) and/or [Prowlarr](https://github.com/Prowlarr/Prowlarr)

2. Install this addon.

3. Add configuration on addon settings to connect with Jackett and/or Prowlarr

4. Add configuration on addon settings to connect with TMDB (Api Key).

5. Install Torrest service (torrent client which provides an API specially made for streaming). [Torrest Service](https://github.com/i96751414/torrest-cpp)

6. Install Torrest addon. [Torrest](https://github.com/i96751414/plugin.video.torrest)

7. Configure Torrest addon with the Torrest service that you deployed on step 5.


**Note**:

- You can deploy Prowlarr and Jackett either on local or on a remote server.
- You can deploy the Torrest service either on local or on a remote server or use the built-in torrent service from addon that runs on localhost.

## Installation of this addon (Jackewlarr)

The recommended way of installing the addon is through its [repository](https://github.com/Sam-Max/repository.jackewlarr), so that any updates will be automatically installed.

You can also install the addon without installing its repository. To do so, get the [latest release](https://github.com/Sam-Max/plugin.video.jackewlarr/releases/download/v0.0.4/plugin.video.jackewlarr-0.0.4.zip) from github. Please note that, if there are any additional dependencies, they won't be resolved unless the repository is installed.

## How to run Jackett service using Docker:

Detailed instructions are available at [LinuxServer.io Jackett Docker](https://hub.docker.com/r/linuxserver/jackett/) 


## How to run Prowlarr service using Docker:

Detailed instructions are available at [Prowlarr Website](https://prowlarr.com/#downloads-v3-docker) 


## How to run Torrest service using Docker:

1. Create a Dockerfile with the following content (make sure to check before the latest `VERSION` of the binary and your `OS` and `ARCH` and update accordingly).

```
FROM ubuntu:latest

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

![](https://raw.githubusercontent.com/Sam-Max/plugin.video.jackewlarr/master/resources/screenshots/jackewlarr.png)

## Legal Disclaimer:

This addon should only be used to access movies and TV shows not protected by copyright

