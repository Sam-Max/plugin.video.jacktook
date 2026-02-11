from lib.utils.kodi.utils import (
    action_url_run,
    kodi_play_media,
    translation,
)
import json


def add_last_files_context_menu(data):
    from lib.utils.general.utils import IndexerType

    menu_items = []

    if data.get("type") != IndexerType.STREMIO_DEBRID:
        menu_items.append(
            (
                translation(90084),
                action_url_run(
                    "resolve_for_pack_selection",
                    data=json.dumps(data),
                ),
            )
        )

    menu_items.extend(
        [
            (
                translation(90083),
                action_url_run(
                    name="download_video",
                    data=json.dumps(data),
                ),
            ),
            (
                translation(90082),
                kodi_play_media(
                    "resolve_for_subtitles",
                    data=json.dumps(data),
                ),
            ),
        ]
    )

    return menu_items
