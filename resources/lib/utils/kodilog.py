import logging

import xbmc
import xbmcaddon

ADDON_ID = xbmcaddon.Addon().getAddonInfo("id")


def level_to_kodi(level):  # type: (int) -> int
    return (level - logging.DEBUG) // 10


class KodiHandler(logging.Handler):
    def emit(self, record):  # type: (logging.LogRecord) -> None
        msg = self.format(record)
        xbmc.log(msg, level_to_kodi(record.levelno))


def strip_prefix(s, prefix):  # type: (str, str) -> str
    if s.startswith(prefix):
        return s[len(prefix):]
    return s


_COMMON_PREFIX = "resources.lib."


class KodiFormatter(logging.Formatter):
    def format(self, record):  # type: (logging.LogRecord) -> str
        record.name = strip_prefix(record.name, _COMMON_PREFIX)
        record.addon_id = ADDON_ID
        return super(KodiFormatter, self).format(record)


def setup_logging():  # type: () -> None
    logger = logging.getLogger()
    # TODO find a way to get current level from kodi
    logger.setLevel(logging.DEBUG)
    handler = KodiHandler()
    handler.setFormatter(KodiFormatter("[%(addon_id)s] %(name)s: %(message)s"))
    logger.addHandler(handler)
