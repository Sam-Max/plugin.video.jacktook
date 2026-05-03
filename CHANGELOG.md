## 1.13.0
- Downloads: Add a downloads manager for managing downloaded files inside Jacktook.
- External Scraper: Add generic external scraper module support for addons like Magneto, CocoScrapers, etc, with settings and configuration dialog.
- TMDB: Add configurable excluded languages filter for hiding content in selected original languages.
- Search: Add a loading spinner while sources resolve and improve stale-cache fallback behavior.
- Source Manager: Auto-select newly enabled sources so provider changes take effect immediately.
- Burst: Harden result parsing and internal imports for safer provider integration.
- Localization: Fix missing and misaligned Romanian strings and improve Romanian translations.

Spanish:
- Descargas: Añadido gestor de descargas para administrar archivos descargados dentro de Jacktook.
- Scraper Externo: Añadido soporte genérico de módulo de scraper externo para addons como Magneto, CocoScrapers, etc, con ajustes y diálogo de configuración.
- TMDB: Añadido filtro configurable de idiomas excluidos para ocultar contenido en idiomas originales seleccionados.
- Busqueda: Añadido spinner de carga mientras se resuelven las fuentes y mejorado el fallback de cache obsoleta.
- Source Manager: Seleccion automatica de fuentes recien activadas para que los cambios de proveedores apliquen inmediatamente.
- Burst: Reforzado el parseo de resultados y las importaciones internas para una integracion de proveedores mas segura.
- Localizacion: Corregidas cadenas rumanas faltantes y desalineadas y mejoradas las traducciones al rumano.

Note:
If you enjoy this addon, please consider supporting the project with a donation. Your contributions help keep improving and maintaining it. Thank you!

Si disfrutas de este addon, por favor considera apoyar el proyecto con una donación. Tus contribuciones ayudan a seguir mejorándolo y manteniéndolo. ¡Gracias!

Dacă îți place acest add-on, te rog să iei în considerare susținerea proiectului printr-o donație. Contribuțiile tale ajută la îmbunătățirea și menținerea acestuia. Mulțumesc!

Если вам нравится этот аддон, пожалуйста, подумайте о поддержке проекта пожертвованием. Ваш вклад помогает улучшать и поддерживать его. Спасибо!

Se você gosta deste addon, considere apoiar o projeto com uma doação. As suas contribuições ajudam a continuar melhorando e mantendo-o. Obrigado!

## 1.12.0
- Services: Add AutoStart service to automatically open Jacktook when Kodi boots (optional toggle in Settings > General > Startup).
- Services: Add WidgetRefresh background service to periodically refresh Kodi widgets on a configurable timer (0-180 minutes) with optional notifications.
- IMDb/Extras: Replace regex-based IMDb scraping with stable GraphQL API. Now fetches user reviews (with ratings, dates, and spoiler warnings), trivia, goofs/blunders, and structured parental guide (Sex & Nudity, Violence & Gore, Profanity, Alcohol/Drugs/Smoking, Frightening & Intense Scenes) in a single request.
- IMDb/Extras: Add IMDb user reviews to the Extras window alongside existing TMDB reviews and Trakt comments.
- TMDB/Search: Add TV show title-year search mode for finding shows by title and year.
- TMDB/Cache: Resolve language change and cache issues. Improve cache invalidation, English fallback behavior, and TMDB initialization after settings changes.
- TMDB/UI: Reorder manage sources context item for better menu organization.
- Localization: Add Romanian language support

Spanish:
- Servicios: Añadido servicio AutoStart para abrir Jacktook automaticamente al arrancar Kodi (interruptor opcional en Ajustes > General > Inicio).
- Servicios: Añadido servicio WidgetRefresh en segundo plano para actualizar widgets de Kodi periodicamente con un temporizador configurable (0-180 minutos) y notificaciones opcionales.
- IMDb/Extras: Reemplazado el scraper regex de IMDb por la API GraphQL estable. Ahora obtiene reviews de usuarios (con ratings, fechas y advertencias de spoilers), trivia, errores/blunders, y guia parental estructurada (Sexo y Desnudez, Violencia y Sangre, Lenguaje, Alcohol/Drogas/Tabaco, Escenas Aterradoras e Intensas) en una sola peticion.
- IMDb/Extras: Añadidas reviews de usuarios de IMDb en la ventana Extras junto a las reviews de TMDB y comentarios de Trakt.
- TMDB/Busqueda: Añadido modo de busqueda por titulo-ano para series de TV.
- TMDB/Cache: Resueltos problemas de cambio de idioma y cache. Mejorada invalidacion de cache, fallback en ingles e inicializacion de TMDB tras cambios de ajustes.
- TMDB/UI: Reordenado el item de contexto "manage sources" para mejor organizacion del menu.
- Localizacion: Añadido soporte para rumano.


## 1.11.0
- Source Manager: Add a dialog to enable or disable individual stream sources/providers.
- Playback: Add Autoscrape Next Episode with resolved playback caching for faster next-episode playback.
- Playback: Add stinger/post-credit scene notifications for movies with during-credits or after-credits scenes.
- TMDB/Artwork: Add image resolution tiers for TMDB artwork.
- Posters: Add RPDB integration for rating posters.
- Filters: Add Codec, HDR, and Dolby Vision filters for search results.
- Downloads: Add resumable downloads with movie/TV folder organization.
- Torrents: Add subtitle download and playback from TorrServer torrent and file context menus.
- Playback: Route TorrServer file clicks and subtitle playback through Jacktorr `Play Torrent`/`buffer_and_play` so buffering, pause statistics, and resume work correctly.
- Source Select: Remove Download Video from torrent source context menus and add Download subtitles.
- Localization: Rename Buffer and play to Play Torrent and add localized missing-metadata messages.

Spanish:
- Source Manager: Añadido dialogo para activar o desactivar fuentes/proveedores de streams individualmente.
- Reproduccion: Añadido Autoscrape Next Episode con cache de reproduccion resuelta para acelerar la reproduccion del siguiente episodio.
- Reproduccion: Añadidas notificaciones de escenas post-creditos/stinger para peliculas con escenas durante o despues de los creditos.
- TMDB/Arte: Añadidos niveles de resolucion para imagenes de TMDB.
- Posters: Añadida integracion con RPDB para posters con ratings.
- Filtros: Añadidos filtros de Codec, HDR y Dolby Vision para resultados de busqueda.
- Descargas: Añadidas descargas reanudables con organizacion de carpetas para peliculas/series.
- Torrents: Añadida descarga y reproduccion de subtitulos desde los menus contextuales de torrents y archivos de TorrServer.
- Reproduccion: Enrutados los clicks de archivos TorrServer y la reproduccion con subtitulos por Jacktorr `Play Torrent`/`buffer_and_play` para mantener buffering, estadisticas al pausar y reanudacion.
- Source Select: Eliminada la opcion Descargar Video de fuentes torrent y añadida Descargar subtitulos.
- Localizacion: Renombrado Buffer and play a Play Torrent y añadidos mensajes localizados para metadata faltante.

## 1.10.0
- Search: Add Search Title Language mode with localized first, English first, and English only ordering for Easynews/Jackett/Prowlarr context searches.
- Search: Improve English-first fallback behavior to prioritize TMDB original titles before localized titles when English translations are missing.
- Search/Cache: Scope search and debrid cache entries by active provider/addon state to avoid stale cross-provider reuse.
- Source Select: Improve source labeling clarity for search results.
- Playback/TorrServer: Harden torrent URL handling for Jackett sources and preserve movie year in generated download filenames.
- TMDB: Fix multi-search movie context actions.
- UX: Keep source focus cache outside addon settings to avoid unintended persistence issues.

Spanish:
- Busqueda: Añadido modo de idioma del titulo de busqueda con orden Localizado primero, Ingles primero y Solo ingles para busquedas de contexto en Easynews/Jackett/Prowlarr.
- Busqueda: Mejorado el comportamiento de fallback en Ingles primero para priorizar el titulo original de TMDB antes del titulo localizado cuando falta traduccion al ingles.
- Busqueda/Cache: Segmentada la cache de busqueda y debrid por estado activo de proveedores/addons para evitar reutilizacion obsoleta entre proveedores.
- Seleccion de fuentes: Mejorada la claridad del etiquetado de fuentes en los resultados.
- Reproduccion/TorrServer: Reforzado el manejo de URLs torrent para fuentes de Jackett y conservado el año de pelicula en los nombres de descarga generados.
- TMDB: Corregidas las acciones de contexto de multi-busqueda para peliculas.
- UX: Movida la cache de foco de fuente fuera de los ajustes del addon para evitar persistencia no deseada.

## 1.9.0
- Subtitle: Add subtitle upload from device or from a local webserver.
- Downloads: Preserve the file extension and episode info in downloaded filenames.
- Torrents: Fix torrent file handoff to TorrServer for Jackett trackers like Filelist.
- UI: Stop the fallback poster viewtype from overriding the user's preference.

Spanish:
- Subtitulos: Añade la subida de subtitulos desde el dispositivo o desde un servidor web local.
- Descargas: Conserva la extension y la informacion del episodio en los nombres descargados.
- Torrents: Corrige el envio de archivos torrent a TorrServer para trackers de Jackett como Filelist.
- UI: Evita que la vista de poster de respaldo sobrescriba la preferencia del usuario.

## 1.8.0
- Search: Add TMDB Search Modes for movies and episodes, including title editing, original title variants, and manual year/season/episode entry from TMDB context menus.
- Performance: Rework menu and listing rendering with batch `addDirectoryItems`, `ListItem(offscreen=True)`, `reuselanguageinvoker`, cached navigator entries, and cached TMDB item metadata to improve navigation speed
- TMDB: Remove repeated per-item image/detail rebuilding in major list views and avoid duplicate show-detail fetches in Calendar.
- Settings: Cache addon settings from a profile `settings.xml` snapshot so changes made in Kodi settings are reflected more reliably across the addon.
- Debrid/Cloud: Cache cloud download listings, move Cloud account info out of problematic list navigation, and improve cloud/provider modal flows.
- UX: Fix multiple stuck spinner cases across Settings, Torrents, Jackgram, TMDB/MDblist search cancel flows, search history actions, and debrid account dialogs.
- Easynews: Fix the account info dialog heading import so the modal opens without errors.
- Improve and harden addon downgrade and added reload profile after addon update
- Moved view selection controls into the addon settings menu.

Spanish:
- Busqueda: Añadidos Modos de busqueda de TMDB para peliculas y episodios, incluyendo edicion de titulo, variantes con titulo original y entrada manual de ano/temporada/episodio desde los menus contextuales de TMDB.
- Rendimiento: Rehecha la representacion de menus y listados con `addDirectoryItems` por lotes, `ListItem(offscreen=True)`, `reuselanguageinvoker`, cache de entradas del navigator y cache de metadatos TMDB por item para mejorar la velocidad de navegacion.
- TMDB: Eliminada la reconstruccion repetida de imagenes/detalles por item en los principales listados y evitadas las consultas duplicadas de detalles de series en Calendar.
- Ajustes: Añadida cache de ajustes del addon a partir de un snapshot del `settings.xml` del perfil para reflejar con mas fiabilidad los cambios hechos desde los ajustes de Kodi.
- Debrid/Cloud: Añadida cache a los listados de descargas cloud, movida la informacion de cuenta de Cloud fuera de la navegacion problematica del listado y mejorados los flujos modales de cloud/proveedores.
- UX: Corregidos multiples casos de spinner bloqueado en Ajustes, Torrents, Jackgram, cancelaciones de busqueda TMDB/MDblist, acciones del historial de busqueda y dialogos de informacion de cuenta de debrid.
- Easynews: Corregida la importacion del titulo del dialogo de informacion de cuenta para que el modal se abra sin errores.
- Mejorada y reforzada la seguridad de la funcion de downgrade y añadida la recarga del perfil despues de la actualizacion del addon.
- Movidos los controles de seleccion de vista al menu de ajustes del addon.

## 1.7.2
- Trailers: Add YouTube trailer playback flow.
- Playback: Add setting to skip the replay/resume dialog.
- Settings: Add per-section view settings and improve description length handling by allowing `0` and applying truncation correctly.
- Stremio: Preserve catalog metadata, exact addon routes, exact season routes, and improve catalog search history flows.
- Stremio: Speed up catalog menus and keep search results bound to the correct addon route.
- Library: Keep Stremio entries linked to Stremio metadata, add `clear all` actions, and improve timestamp parsing robustness.
- Debrid: Harden source handling across providers and fix Premiumize authorization issues.
- Search: Remove Zilean search task handling.

Spanish:
- Trailers: Añadida la reproduccion de trailers de YouTube.
- Reproduccion: Añadido ajuste para omitir el dialogo de reanudacion/repeticion.
- Ajustes: Añadidos ajustes de vista por seccion y mejorado el manejo de la longitud de descripcion permitiendo `0` y aplicando truncado correctamente.
- Stremio: Conserva metadatos del catalogo, rutas exactas de addons, rutas exactas de temporadas y mejora los flujos del historial de busqueda del catalogo.
- Stremio: Aceleracion de los menus del catalogo y mantiene los resultados de busqueda vinculados a la ruta correcta del addon.
- Biblioteca: Mantiene las entradas de Stremio enlazadas a sus metadatos, añade acciones de `clear all` y mejora la robustez del parseo de timestamps.
- Debrid: Refuerza el manejo de fuentes entre proveedores y corrige problemas de autorizacion con Premiumize.
- Busqueda: Eliminado el manejo de tareas de busqueda de Zilean.

## 1.7.1
- Localization: Add Russian language support and expand/update translations for Spanish, Russian, and Portuguese.
- UI: Replace remaining hardcoded dialog text with translated strings.
- AllDebrid: Keep the authorization dialog open during reauthorization when a previous token exists.
- Playback: Make the skip intro/recap popup interactive so the user can manually trigger the skip action.
- Stremio: Show `Local URL` instead of `Pastebin Link` in Manage from Phone QR dialogs.
- Updater: Clarify automatic update action handling and preserve explicit `Ask`, `Notify`, and `None` modes.

Spanish:
- Localizacion: Añadido soporte para ruso y ampliadas/actualizadas las traducciones de espanol, ruso y portugues.
- UI: Sustituidos los textos de dialogos que quedaban hardcodeados por cadenas traducidas.
- AllDebrid: Mantiene abierto el dialogo de autorizacion durante la reautorizacion cuando existe un token previo.
- Reproduccion: Hace interactivo el popup de saltar intro/recap para que el usuario pueda ejecutar manualmente el salto.
- Stremio: Muestra `URL local` en lugar de `Pastebin Link` en los dialogos QR de Manage from Phone.
- Actualizador: Aclara el manejo de acciones de actualizacion automatica y mantiene los modos explicitos `Ask`, `Notify` y `None`.

## 1.7.0
- Torrents: Add source actions to send torrents directly to Debrid cloud or TorrServer from the source select menu.
- Torbox: Add Cloud downloads browsing.
- Downloads: Fix `Download video` routing so source downloads start correctly.
- Filters: Fix unknown source filtering and add a separate toggle for unknown quality results.
- Debrid: Block direct playback of packed releases (zip, rar, etc) across debrid providers.
- Fix: Update TMDBHelper json when outdated.
- TMDB: Fix the Collections menu circular import crash.
- Fix Prowlarr client search failing when receiving season and episode from TMDBHelper.

Spanish:
- Torrents: Añadidas acciones en la seleccion de fuentes para enviar torrents directamente a la nube de Debrid o a TorrServer.
- Torbox: Añadida navegacion de descargas en Cloud.
- Descargas: Corregido el enrutado de `Download video` para que las descargas desde fuentes se inicien correctamente.
- Filtros: Corregido el filtrado de fuentes desconocidas y añadido un ajuste independiente para calidad desconocida.
- Debrid: Bloqueada la reproducción directa de lanzamientos empaquetados (zip, rar, etc) en los proveedores de debrid.
- Corregida la actualización del json de TMDBHelper cuando está desactualizado.
- TMDB: Corregido el fallo por importacion circular en el menu de Collections.
- Corregido el fallo en la búsqueda del cliente de Prowlarr al recibir temporada y episodio de TMDBHelper.

## 1.6.0
- Search: Add English TMDB title fallback for Jackett and Prowlarr when localized titles return no matches.
- Playback: Handle magnet redirects and torrent URLs from indexers more reliably.
- Search: Fix result sorting across all sort modes.
- Search: Clarify the final no-results notification when no playable sources remain.
- UI: Hide peers and seeders metadata when a source is already cached.

Spanish:
- Busqueda: Anadido fallback al titulo en ingles de TMDB para Jackett y Prowlarr cuando los titulos localizados no devuelven coincidencias.
- Reproduccion: Mejorado el manejo de redirecciones magnet y URLs torrent de indexadores.
- Busqueda: Corregida la ordenacion de resultados en todos los modos de ordenacion.
- Busqueda: Aclarada la notificacion final cuando no quedan fuentes reproducibles.
- UI: Ocultados los metadatos de peers y seeders cuando una fuente ya esta en cache.

## 1.5.3
- Trakt: Add 'Continue Watching' option for movies to easily resume playback.
- Trakt: Fix Unprocessable Entity (422) error when scrobbling items with no playback progress.
- Trakt: Filter hidden items in Up Next and remove list limits.
- UI: Overhaul source select window with advanced technical metadata, modern layout, and dynamic color themes.
- Stremio: Improve source labeling to show real indexer names.
- Torbox: Fix authentication response parsing.
- Settings: Add Trakt credentials migration and update defaults.

Spanish:
- Trakt: Añadida opción 'Continuar Viendo' para películas para reanudar fácilmente la reproducción.
- Trakt: Corregido error 'Unprocessable Entity' (422) al registrar progreso (scrobbling) de elementos sin avance.
- Trakt: Filtrar elementos ocultos en Up Next y eliminar límites de listas.
- UI: Renovación de la ventana de selección de fuentes con metadatos técnicos avanzados, diseño moderno y temas de color dinámicos.
- Stremio: Mejorado el etiquetado de fuentes para mostrar los nombres reales de los indexadores.
- Torbox: Corregido el análisis de la respuesta de autenticación.
- Ajustes: Añadida migración de credenciales de Trakt y actualizados los valores por defecto.


## 1.5.2
- Stremio: Distinguish addon instances by transport URL to support multiple accounts/configurations of the same addon with different flows.
- Stremio: Support bypassing specific addon instances from Jacktook's filtering.
- Settings: Reorganize backup options and add URL restore

Spanish:
- Stremio: Diferenciación de instancias de addons por URL de transporte para soportar múltiples cuentas/configuraciones del mismo addon con diferentes flujos.
- Stremio: Soporte para omitir el filtrado de Jacktook en instancias específicas de addons.
- Ajustes: Reorganización de las opciones de backup y añadido restauración por URL.


## 1.5.1
- Stremio: Limit imported addons to account and custom sources and improved large catalog handling.
- Settings: Simplify Stremio-related visibility rules, remove the old Torrentio settings group, and set safer disabled-by-default values for Stremio, torrents, and bypassed addons.
- Localization: Fix conflicting string IDs.

Spanish:
- Stremio: Limitadas las importaciones de addons a las fuentes de cuenta y personalizadas y mejorado el manejo de catalogos grandes.
- Ajustes: Simplificadas las reglas de visibilidad relacionadas con Stremio, eliminado el antiguo grupo de ajustes de Torrentio y establecidos valores mas seguros desactivados por defecto para Stremio, torrents y addons omitidos.
- Localizacion: Corregidos los IDs de cadenas en conflicto.

## 1.5.0
- Trakt Expansion: Added personal lists, search lists by keyword, create custom lists, favorites, account info.
- Enhanced Trakt Sync: Improved scrobbling, progress tracking, and added periodic syncing service.
- Added backup/reset tool for addon settings.
- Modernized routing, provider registries, and service-based auth flows.
- Fix Update flow that was partially broken cause of using incorrect addon identifier.
- Improved scrobbler notifications and calendar item rendering.
- Aligned logging with Kodi levels.
- Other minor improvements.

Spanish:
- Expansión de Trakt: Añadidas listas personales, búsqueda de listas por palabra clave, creación de listas personalizadas, favoritos, información de la cuenta.
- Sincronización mejorada de Trakt: Mejor scrobbling, seguimiento del progreso y servicio de sincronización periódica añadido.
- Añadida herramienta de respaldo/restablecimiento de los ajustes del addon.
- Modernizado el enrutamiento, los registros de proveedores y los flujos de autenticación basados en servicios.
- Corregido el flujo de actualización que estaba parcialmente roto debido al uso de un identificador del addon incorrecto.
- Mejoradas las notificaciones del scrobbler y la representación de los elementos del calendario.
- Alineado el registro con los niveles de Kodi.
- Otras mejoras menores.

## 1.4.4

- Real-Debrid: Fix multi-file movie torrents by selecting the largest playable file
- Split subtitle feedback so missing subtitles and unselected subtitles show different messages.
- Localize subtitle download dialogs and subtitle status notifications.

Spanish:

- Real-Debrid: Corregidos los torrents de peliculas con multiples archivos seleccionando el archivo reproducible mas grande.
- Separados los mensajes de subtitulos no encontrados y subtitulos no seleccionados.
- Localizados los dialogos de descarga de subtitulos y las notificaciones de estado de subtitulos.

## 1.4.3

- Improve loading speed for My Movies and My Shows by caching resolved library views.
- Fix Continue Watching and Last Files labels when season or episode values are stored as strings.
- Stremio: Fix scoped searches for TMDB-only addons and improve addon compatibility detection in the local web manager.
- Stremio: Normalize manifest URLs, add better local HTTP fallback, and mark direct streams correctly for playback.
- Jackett: Increase the configurable timeout range up to 300 seconds.
- Jackgram: Harden latest endpoints and restore title source routing.

Spanish:

- Mejora la velocidad de carga de Mis Peliculas y Mis Series cacheando las vistas de biblioteca ya resueltas.
- Corregidas las etiquetas de Seguir viendo y Ultimos archivos cuando los valores de temporada o episodio se guardan como texto.
- Stremio: Corregidas las busquedas dirigidas para addons que solo usan TMDB y mejorada la deteccion de compatibilidad de addons en el gestor web local.
- Stremio: Normalizadas las URLs de manifest, mejorado el fallback local por HTTP y corregido el marcado de streams directos para la reproduccion.
- Jackett: Aumentado el rango configurable del tiempo de espera hasta 300 segundos.
- Jackgram: Endurecidos los endpoints de ultimos y restaurado el enrutado del origen del titulo.

## 1.4.2

- Add new token setting for Jackgram.
- Refactor internal Jackgram functions based on new API changes.

Spanish:

- Añadida nueva configuración de token para Jackgram.
- Refactorización de funciones internas de Jackgram basado en los nuevos cambios de la API.

## 1.4.1

- Add fullscreen search status window with live task tracking.
- Improve source provider name display for direct indexers.

Spanish:

- Añadida ventana de estado de búsqueda a pantalla completa con seguimiento de tareas en vivo.
- Mejora en la visualización del nombre del proveedor de origen para indexadores directos.

## 1.3.2

- Fix: Easynews crash on Python versions older than 3.9 (e.g. Kodi 20).
- Fix 'No Stremio addon selected' error when adding custom addons with commas in the URL.
- Implement lazy loading for client modules to improve startup performance and stability.
- Improvements to the update flow.

Spanish:

- Corregido: Error de Easynews en versiones de Python anteriores a 3.9 (ej. Kodi 20).
- Corregido error: 'No Stremio addon selected' al añadir addons personalizados con comas en la URL.
- Implementación de carga diferida para los módulos de clientes para mejorar el rendimiento y la estabilidad.
- Mejora del mecanismo de actualización.

## 1.3.1

- Add 'Search by Keyword' functionality for Movies and TV Shows.
- Add Easynews search support.
- Add debrid subscription expiration notifications.
- Add automatic volume safety check before starting playback.
- Open actor info window when selecting a person from People menu.
- Add client key support for Fanart.tv
- Improve updater mechanism with progress visibility and better UI refresh.

Spanish:

- Añadida funcionalidad de 'Búsqueda por palabra clave' para películas y series.
- Añadido soporte de búsqueda en Easynews.
- Añadidas notificaciones de expiración de suscripción de debrid.
- Añadido control automático de seguridad de volumen antes de iniciar la reproducción.
- Abre la ventana de información del actor al seleccionar una persona del menú de Personas.
- Añadido soporte de clave personal para Fanart.tv
- Mejora del mecanismo de actualización con visibilidad del progreso y mejor refresco de la interfaz.

## 1.2.1

- Skin: Add 'Extras' and 'Actor Info' windows to media details.
- Add IMDB scraper for fetching extras and cast information.

Spanish:

- Skin: Añadidas ventanas de 'Extras' e 'Información del actor' a los detalles de los medios.
- Añadido scraper de IMDB para obtener extras e información del reparto.

## 1.1.1

- Stremio: Support multiple configurations of the same addon by identifying them via transport URL.
- Stremio: Increase configurable request timeout range up to 120s and apply it globally to all requests.

Spanish:

- Stremio: Soporte para múltiples configuraciones del mismo addon identificándolos mediante la URL de transporte.
- Stremio: Aumento del rango de tiempo de espera (timeout) configurable hasta 120 segundos y aplicación global a todas las peticiones.

## 1.1.0

- Add 'Downgrade Addon Version' functionality in settings to easily revert to previous releases.
- Add 'Bypass Addon Filters' for selected Stremio addons, allowing them to skip Jacktook's native size/quality filtering.
- Improve metadata resolution and movie detection for Stremio providers.
- Improve Super Quick Play logic with better cache key handling for TV shows and movies.
- Performance optimizations and improved error handling across several modules.

Spanish:

- Añadida función 'Revertir versión del addon' en los ajustes para volver fácilmente a versiones anteriores.
- Añadida funcionalidad 'Omitir filtros de addons' para que los addons de Stremio seleccionados salten el filtrado nativo.
- Mejora en la resolución de metadatos y detección de películas para los proveedores de Stremio.
- Mejora en la lógica de 'Reproducción súper rápida' con un mejor manejo de claves de caché para series y películas.
- Optimizaciones de rendimiento y mejora en el manejo de errores en varios módulos.

## 1.0.0

- Implement lazy loading for router and navigation for better performance.
- Add local web server for managing Stremio addons via phone/browser.
- Add skip intro and recap feature using IntroDB API.
- Add support for Bingie Helper in TMDB auto-installer.
- Add 'Continue Watching' and 'Library' section to main menu.
- Grouped the main menu's 'Search' and 'Direct Search' entries into a single 'Search' menu to reduce clutter.
- Add history management and clear options in the search menu.
- Move the donation menu to addon settings.
- Reordered main menu to place 'Library' below 'Live TV'.
- Fix playback failure when subtitles were not found or selected
- Fix QR code visibility in some custom dialogs (including donation).
- Improved Kodi 21+ compatibility by addressing `setInfo()` deprecations.
- Other minor fixes and improvements.

Spanish:

- Implementación de carga diferida (lazy loading) para el router y la navegación para mejorar el rendimiento.
- Añadido servidor web local para gestionar addons de Stremio desde el teléfono/navegador.
- Añadida función para saltar intros y resúmenes usando la API de IntroDB.
- Añadida compatibilidad con Bingie Helper en el instalador automático de TMDB.
- Añadida sección 'Seguir viendo' y 'Biblioteca' al menú principal.
- Agrupadas las entradas 'Buscar' y 'Búsqueda directa' del menú principal en un único menú 'Buscar' para mejor organizacion.
- Añadido gestión de historial y opciones de borrado en el menú de búsqueda.
- Movido el menú de donaciones a los ajustes del addon.
- Reordenado el menú principal para colocar 'Biblioteca' debajo de 'TV en vivo'.
- Corregido el fallo de reproducción cuando los subtítulos no se encontraban o no se seleccionaban.
- Corregida la visibilidad del código QR en algunos diálogos personalizados (incluyendo donaciones).
- Mejora de la compatibilidad con Kodi 21+ al abordar las depreciaciones de `setInfo()`.
- Otras correcciones menores y mejoras.

## 0.24.0

- Stremio: Add manual addon availability ping and filtering.
- Stremio: Support for movie items with custom IDs.
- TMDB: Add 'Airing Today' section for TV shows.
- TMDB: Display clearlogos in category listings.
- Anime: Add new anime categories.
- Fix: Trakt sync error related to 'set_bulk_tvshow_progress'.
- Fix: Mark Stremio Live TV streams as direct type for proper playback.
- Fix: JacktookBurst using wrong ID type (replace tmdb_id with imdb_id).
- Fix: Routing conflict by renaming internal 'play_media' helper.

## 0.23.0

- Implement hybrid cache and background preloading for better performance.
- Add dedicated selection on Stremio settings for Stremio Live TV addons.
- Add setting to show only Stremio catalogs instead of native catalogs.
- Add granular cache cleaning options.
- Add setting to enable the precaching of next episodes.
- Add Trakt synchronization service, QR code authentication and improved resume capability.
- Reorganized and improved Stremio settings with better grouping.
- Improve Torbox integration with better pack resolution and localization.
- Improve WebDAV connection robustness and fix playback URL issue.
- Improve Stremio addon compatibility and manifest parsing.
- Fix next episode skip bug and prevent player crashes.
- Fix search results loss when P2P is enabled in Stremio.
- Fix duplicate providers in Torrentio URL.
- Fix various issues with Trakt authentication and sync.
- Localize many UI strings.
- Many other internal refactors and improvements to the Stremio client.

Spanish:

- Implementación de caché híbrida y precarga en segundo plano para un mejor rendimiento.
- Añadida en la configuración de Stremio la selección dedicada para addons de TV en vivo.
- Añadido ajuste para mostrar solo catálogos de Stremio en lugar de los catálogos nativos.
- Añadido limpiado granular de caché.
- Añadido ajuste para habilitar la precarga de los siguientes episodios.
- Añadido servicio de sincronización con Trakt, autenticación con QR y mejora en la capacidad de reanudación.
- Reorganización y mejora de los ajustes de Stremio con una mejor agrupación.
- Mejora en la integración con Torbox, con mejor resolución de paquetes y localización.
- Mejora en la robustez de la conexión WebDAV y corrección del error en la URL de reproducción.
- Mejora en la compatibilidad de addons de Stremio y el análisis del manifest.
- Corregido el error de salto al siguiente episodio y prevención de cuelgues del reproductor.
- Corregida la pérdida de resultados de búsqueda cuando P2P está habilitado en Stremio.
- Corregida la duplicación de proveedores en la URL de Torrentio.
- Corregidos varios problemas con la autenticación y sincronización de Trakt.
- Localización de varias cadenas de la interfaz.
- Muchas otras refactorizaciones internas y mejoras en el cliente de Stremio.

## 0.22.0

- Add super quick play feature (last played dialog) for faster playback.
- Add torrent and debrid filter options on source select window.
- Add precaching of next episodes with settings option.
- Add automatic subtitle selection.
- Add broadcast day adjustment setting for the weekly calendar.
- Add context menu actions for last files
- Add context menu actions for weekly calendar episodes
- Implement accurate search progress indicator.
- Fix search with non-ASCII characters.
- Improve magnet link extraction from torrent files.

Spanish:

- Añadida función de reproducción súper rápida (diálogo de última reproducción) para una reproducción más veloz.
- Añadidas opciones de filtrado de torrent y debrid en la ventana de selección de fuente.
- Añadida precarga (precaching) de los siguientes episodios con opción en los ajustes.
- Añadida selección automática de subtítulos.
- Añadido ajuste del día de emisión para el calendario semanal.
- Añadidas acciones del menú contextual para los últimos archivos.
- Añadidas acciones del menú contextual para los episodios del calendario semanal.
- Implementado un indicador preciso del progreso de búsqueda.
- Corregida la búsqueda con caracteres no ASCII.
- Mejorada la extracción de enlaces magnet de archivos torrent.

## 0.21.0

- Implemented parallel Debrid/P2P resolution.
- Redesigned settings for more intuitive setup.
- Fixed next dialog triggering at wrong time in player.
- Enhanced update notifications for better user feedback.
- Other minor fixes and improvements.

## 0.20.0

- Added functionality to remove custom addons from settings.
- Fixed subtitle translation not working.

## 0.19.0

- Added WebDAV client integration with browsing and playback support.
- Improved magnet extraction and fixed URLs not being passed correctly to torrent clients.
- Increased the default maximum size and adjusted the slider step for better control.
- Added configurable timeout setting for Stremio requests.
- Removed debrid cached search logic to avoid inconsistencies.
- Fixed correct values display for addons like UsenetStreamer.
- Fixed correct rendering of addons names on source selection when using AIOStreams addon.
- Other minor fixes and improvements.

## 0.18.0

- Rewrite TMDB directory handling to include full metadata only when needed and simplify search result rendering.
- Add automatic subtitle download and improved storage/retrieval for individual episodes.
- Automatically convert URLs starting with stremio:// to https:// when adding custom addons.
- Fix Jackett search not working when a password is set
- Other minor fixes and improvements.

Spanish:

- Reescritura del manejo de directorios de TMDb para incluir solo los metadatos completos cuando sea necesario y simplificar la visualización de resultados de búsqueda.
- Añadida descarga automática de subtítulos y mejora en el almacenamiento/recuperación de episodios individuales.
- Conversión automática de URLs que comienzan con stremio:// a https:// al añadir addons personalizados.
- Corrección en la búsqueda de Jackett cuando se establece una contraseña.
- Otras mejoras y correcciones menores.

Note:
Si disfrutas de este addon, por favor considera apoyar el proyecto con una donación. Tus contribuciones ayudan a seguir mejorándolo y manteniéndolo. ¡Gracias!

If you enjoy this addon, please consider supporting the project with a donation. Your contributions helps keep improving and maintaining it. Thank you!

## 0.17.0

- Add AllDebrid support
- Add cached search for AllDebrid
- Fix RealDebrid episodes match not reliable.
- Other minor fixes and improvements.

Spanish:

- Se añadió soporte para AllDebrid
- Se añadió búsqueda con caché para AllDebrid
- Se arreglo errores con la coincidencia de episodios en RealDebrid que no era 100% fiable.
- Otras mejoras y correcciones menores.

Note:
Si disfrutas de este addon, por favor considera apoyar el proyecto con una donación. Tus contribuciones ayudan a seguir mejorándolo y manteniéndolo. ¡Gracias!

If you enjoy this addon, please consider supporting the project with a donation. Your contributions helps keep improving and maintaining it. Thank you!

## 0.16.0

- Add TMDB logo support for clearlogo.
- Prowlarr: add parallel query execution and refined TV search.
- Jackett: add multi-indexer parallel search and improved URL building.
- Add port configuration on settings for Jackett and Prowlarr clients.
- Enhance season pack pattern matching with additional regex options.
- Stremio/UI: add Rutor provider and localized title for Torrentio provider selection.
- Player: notify and handle missing magnet or URL.
- Fanart: simplify fanart fetching.
- Updater: replace dialog_ok with a notification for “no update” messages.
- Skin: refactor resolver.xml layout and adjust clearlogo/fanart positioning.
- Skin: minor UI layout improvements in resolver window and clearlogo positioning.
- Better grouping of addon and settings configuration options.
- Many other minor fixes and improvements.

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

- Hotfix: not detecting season pack when using debrid

## 0.4.9

- Add Priority Language selection setting to filter results.
- Fix missing some supported Stremio Addons.
- Fix autoplay

## 0.4.8

- Add support to import Stremio Addons from Stremio.io Account.

## 0.4.7

- Add Peerflix indexer support.
- Fix Mediafusion not playing sources when using torrents
- Other minor improvements and fixes

## 0.4.6

- Fix a bug that was causing fanart media details not been updating correctly

## 0.4.5

- Add language and region selection setting for TMDB.
- Fix RealDebrid episode selection on season packs
- Fix and handle torrents where its url redirects to magnets.
- Refactor settings.xml to new Kodi format.
- Other minor improvements and fixes

## 0.4.4

- some fixes and improvements

## 0.4.3

- Add search capability across multiple indexers
- Add filter by episode and season option
- Some visual improvements for Arctic Horizon 2 skin.
- Other minor improvements and fixes

## 0.4.2

- Add Telegram menu (with option to enable/disable) with submenus to access Jackgram cached files (for advanced users)
- Add Anime year and genre search.
- Add TMDB year search for TV and Movies.
- Add Trakt popular lists.
- Some visual improvements on direct search source selection.
- Others minor improvements and fixes.

## 0.4.1

- Add play next dialog for episodes playback
- Add automatic playlist creation for shows episodes.
- Update tmdb helper to work with the new routing system.
- Update Jackgram Indexer.
- Others minor improvements and fixes.

## 0.4.0

- Add custom source select and resolve windows dialog.
- Improvements and fixes.

## 0.3.9

- Add EasyDebrid support.
- Add MediaFusion indexer.

## 0.3.8

- Real Debrid Improvements.
  - check if the torrent is on user torrents list, so not to add again.
  - add a check for max activate downloads, and delete one if limit achieved.
- Direct Search Improvements.
  - save search queries, and added menu item option to modify search queries by the user
- Torbox Improvements
  - use public ip address of user for torbox cdn selecction
- Multi Debrid Search support
- Add jackgram_results_per_page setting option for Jackgram client.

## 0.3.7

- Update Premiumize.
- Update Zilean (now supports movies and tv search)
- Update TMDB Helper json file with zip file

## 0.3.6

- Fix tmdb movies results not showing on main search
- Improve Jackett/Prowlarr integration with Debrid for faster results
- Add mechanism to detect indexers change when making a search
- Minor fixes and improvements.

## 0.3.5

- Fix Real Debrid Authentification not working
- Add Real Debrid remove authorization button and username info on settings
- Add option to select Kodi language for TMDB metadata.
- Playback improvements

## 0.3.4

- Improvements on Torbox

## 0.3.3

- Refactor Real Debrid due to recent API changes
- Fixed Torrentio not getting results
- Improvements on Torbox
- Other minor improvements and fixes

## 0.3.2

- Switch to tmdb and trakt for Anime section
- Add Jackgram Support
- Remove Plex Support
- Bug fixes and improvements

## 0.3.1

- Add "rescrape item" context menu item to anime shows results
- Several bug fixes and some improvements

## 0.3.0

- Add Trakt support with several categories
- Update on genres menu and zilean indexer

## 0.2.9

- Add Zilean indexer support
- Minor bug fixes

## 0.2.8

- Add resume playback for videos
- Add new icons for main menu

## 0.2.7

- add "check if pack" context menu item
- several fixes and improvements

## 0.2.6

- Added service for auto-update addon
- Added update addon setting action
- Whole refactoring of jacktook repository

## 0.2.5

- Added Plex support (beta)
- Added support for torbox debrid
- Major anime improvements
- Faster debrid fetch

## 0.2.4 (2024-04-12)

- Added jacktorr burst support
- Improvements on torrent fetch (faster resolve)
- Other minor improvements and fixes

## 0.2.3 (2024-04-06)

- Added jacktorr torrent client support
- Added jacktorr managment from addon instead of torrest
- Other minor improvements and fixes

## 0.2.2 (2024-03-22)

- Added autoplay feature
- Added clients timeouts and cache activation settings
- Added new Tmdb helper addon json
- Torrentio language improvements
- Fixed kodi 19 compatibility
- Other minor improvements and fixes

## 0.2.1 (2024-03-12)

- torrentio improvements (priority language, sort by language, etc)
- added portugese translation
- added trakt scrobbling support
- others improvements and fixes

## 0.2.0 (2024-03-04)

- Add option to select and use all torrents clients at the same time.
- Add pagination to tmdb and anilist search
- Fix for real debrid download history issue (only played videos will be saved)

## 0.1.9 (2024-02-21)

- Fixed RD torrent stored on cloud
- Add sort by quality to torrentio and elfhosted

## 0.1.8 (2024-02-21)

- Add TMDB helper Addon support
- Add new torrents menu
- Add Elementum as another torrent client

## 0.1.7 (2024-02-21)

- Add anime episode search
- Add Premiumize support
- Add Elfhosted support

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
