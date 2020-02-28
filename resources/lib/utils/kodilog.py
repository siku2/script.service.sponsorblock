import logging

import xbmc
import xbmcaddon

ADDON_ID = xbmcaddon.Addon().getAddonInfo("id")


def level_to_kodi(level):  # type: (int) -> int
    return level // 10


class KodiHandler(logging.Handler):
    def emit(self, record):  # type: (logging.LogRecord) -> None
        msg = self.format(record)
        xbmc.log(msg, level_to_kodi(record.levelno))


def setup_logging():  # type: () -> None
    logger = logging.getLogger()
    # TODO get level from kodi
    logger.setLevel(logging.DEBUG)
    handler = KodiHandler()
    handler.setFormatter(logging.Formatter("[{}] %(name)s %(message)s".format(ADDON_ID)))
    logger.addHandler(handler)
