import xbmcaddon

ADDON = xbmcaddon.Addon()

_SETTING_TYPES_MAP = {
    str: (ADDON.getSettingString, ADDON.setSettingString),
    bool: (ADDON.getSettingBool, ADDON.setSettingBool),
    int: (ADDON.getSettingInt, ADDON.setSettingInt),
    float: (ADDON.getSettingNumber, ADDON.setSettingNumber),
}


def get_config(key, cls):  # type: (str, type) -> Any
    fget, _ = _SETTING_TYPES_MAP[cls]
    return fget(key)


def set_config(key, value):  # type: (str, Any) -> bool
    try:
        _, fset = _SETTING_TYPES_MAP[type(value)]
    except KeyError:
        for key in _SETTING_TYPES_MAP:
            if not isinstance(value, key):
                continue

            _, fset = _SETTING_TYPES_MAP[key]
            break

    return fset(key, value)
