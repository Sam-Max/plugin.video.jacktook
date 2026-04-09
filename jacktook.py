#!/usr/bin/env python3

from lib.router import addon_router
from lib.utils.kodi.utils import load_saved_view_properties

load_saved_view_properties()
addon_router()
