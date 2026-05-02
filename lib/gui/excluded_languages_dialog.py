import json

import xbmcgui

from lib.clients.tmdb.utils.excluded_languages_data import EXCLUDABLE_LANGUAGES
from lib.utils.kodi.utils import get_setting, set_setting, translation

SETTING_KEY = "excluded_languages"


def open_excluded_languages_dialog():
    current_raw = get_setting(SETTING_KEY, "[]")
    try:
        current = json.loads(current_raw) if current_raw else []
    except (ValueError, TypeError):
        current = []

    options = [lang["name"] for lang in EXCLUDABLE_LANGUAGES]
    preselect = [i for i, lang in enumerate(EXCLUDABLE_LANGUAGES) if lang["id"] in current]

    selected = xbmcgui.Dialog().multiselect(
        translation(90813),
        options,
        preselect=preselect,
    )

    if selected is None:
        return

    new_selection = [EXCLUDABLE_LANGUAGES[i]["id"] for i in selected]
    set_setting(SETTING_KEY, json.dumps(new_selection))
