import xbmc
import xbmcgui

from ..utils.addon import ADDON_PATH

_CLOSE_ACTIONS = {xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU}


class SponsorSkipped(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self._on_unskip = kwargs.pop("on_unskip")  # type: Callable[[], None]
        self._on_report = kwargs.pop("on_report")  # type: Callable[[], None]

        super(SponsorSkipped, self).__init__(*args, **kwargs)

    @classmethod
    def display(cls, on_unskip, on_report):
        inst = cls("sponsor_skipped.xml", ADDON_PATH, "default", "1080i",
                   on_unskip=on_unskip,
                   on_report=on_report)
        inst.start()

    def start(self):
        self.doModal()

    def onInit(self):  # type: () -> None
        monitor = xbmc.Monitor()
        for _ in range(5):
            if monitor.waitForAbort(1):
                break

        self.close()

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
        action_id = action.getId()
        if action_id == xbmcgui.ACTION_SELECT_ITEM:
            self.onClick(self.getFocusId())
        elif action_id in _CLOSE_ACTIONS:
            self.close()
