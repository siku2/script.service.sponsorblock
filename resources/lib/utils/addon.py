import logging
import os.path

import xbmcaddon
import xbmcgui

logger = logging.getLogger()

ADDON = xbmcaddon.Addon()

ADDON_ID = ADDON.getAddonInfo("id")
ADDON_NAME = ADDON.getAddonInfo("name")
ADDON_PATH = ADDON.getAddonInfo("path")

RESOURCES_PATH = os.path.join(ADDON_PATH, "resources")
SKINS_PATH = os.path.join(RESOURCES_PATH, "skins")

DEFAULT_SKIN = "Default"
DEFAULT_SKIN_RESOLUTION = "1080i"

_SETTING_TYPES_MAP = {
    str: (ADDON.getSetting, ADDON.setSetting),
    bool: (ADDON.getSettingBool, ADDON.setSettingBool),
    int: (ADDON.getSettingInt, ADDON.setSettingInt),
    float: (ADDON.getSettingNumber, ADDON.setSettingNumber),
}


def get_config(key, cls):  # type: (str, Type[T]) -> T
    fget, _ = _SETTING_TYPES_MAP[cls]
    return fget(key)


def set_config(key, value):  # type: (str, Any) -> bool
    try:
        _, fset = _SETTING_TYPES_MAP[type(value)]
    except KeyError:
        raise TypeError("invalid value type {}: {!r}".format(type(value).__qualname__, value))

    return fset(key, value)


DIALOG = xbmcgui.Dialog()

NOTIFICATION_INFO = xbmcgui.NOTIFICATION_INFO
NOTIFICATION_WARNING = xbmcgui.NOTIFICATION_WARNING
NOTIFICATION_ERROR = xbmcgui.NOTIFICATION_ERROR


def show_notification(msg_id, icon=NOTIFICATION_INFO, timeout=5):  # type: (int, str, int) -> None
    DIALOG.notification(
        ADDON_NAME, ADDON.getLocalizedString(msg_id),
        icon=icon,
        time=timeout,
        sound=False
    )
