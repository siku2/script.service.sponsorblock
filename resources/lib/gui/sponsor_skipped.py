import logging
import threading

import xbmc
import xbmcgui

from ..utils import addon

logger = logging.getLogger(__name__)

_CLOSE_ACTIONS = {xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU}

AUTO_CLOSE_TIME_IDLE = 10
AUTO_CLOSE_TIME_INTERACTED = 3


class SponsorSkipped(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self._on_unskip = kwargs.pop("on_unskip")  # type: Callable[[], None]
        self._on_report = kwargs.pop("on_report")  # type: Callable[[], None]
        self._on_expire = kwargs.pop("on_expire")  # type: Callable[[], None]

        self.__closed = False
        self.__close_in = 0

        super(SponsorSkipped, self).__init__(*args, **kwargs)

    @classmethod
    def display(cls, on_unskip, on_report, on_expire):
        inst = cls("sponsor_skipped.xml", addon.ADDON_PATH, addon.DEFAULT_SKIN, addon.DEFAULT_SKIN_RESOLUTION,
                   on_unskip=on_unskip,
                   on_report=on_report,
                   on_expire=on_expire)
        inst.doModal()

    @classmethod
    def display_async(cls, *args):
        t = threading.Thread(target=cls.display, name="sponsor skipped dialog",
                             args=args)
        t.start()
        return t

    def __closer(self):
        monitor = xbmc.Monitor()
        self.__reset_close_timer(interacted=False)
        while self.__close_in:
            if monitor.waitForAbort(1) or self.__closed:
                return

            self.__close_in -= 1

        logger.debug("automatically closing window")
        self.close()
        self._on_expire()

    def onInit(self):  # type: () -> None
        self.__closer()

    def close(self):  # type: () -> None
        self.__closed = True
        super(SponsorSkipped, self).close()

    def __reset_close_timer(self, interacted=True):  # type: (bool) -> None
        self.__close_in = AUTO_CLOSE_TIME_INTERACTED if interacted else AUTO_CLOSE_TIME_IDLE

    def onClick(self, control_id):  # type: (int) -> None
        close = True

        if control_id == 1:
            self._on_unskip()
        elif control_id == 2:
            self._on_report()
        else:
            close = False

        if close:
            self.close()

    def onAction(self, action):  # type: (xbmcgui.Action) -> None
        self.__reset_close_timer()

        action_id = action.getId()
        if action_id == xbmcgui.ACTION_SELECT_ITEM:
            self.onClick(self.getFocusId())
        elif action_id in _CLOSE_ACTIONS:
            self.close()
