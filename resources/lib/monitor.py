import logging

import xbmc

from . import youtube_api
from .player_listener import PlayerListener
from .sponsorblock import SponsorBlockAPI
from .sponsorblock.utils import new_user_id
from .utils import addon
from .utils.const import CONF_API_SERVER, CONF_USER_ID

logger = logging.getLogger(__name__)


def get_user_id():
    user_id = addon.get_config(CONF_USER_ID, str)
    if not user_id:
        user_id = new_user_id()
        logger.info("generated new user id: %s", user_id)
        addon.set_config(CONF_USER_ID, user_id)

    return user_id


class Monitor(xbmc.Monitor):
    def __init__(self):
        self._api = SponsorBlockAPI(
            user_id=get_user_id(),
            api_server=addon.get_config(CONF_API_SERVER, str),
        )

        self._player_listener = PlayerListener(api=self._api)

    def stop(self):
        self._player_listener.stop()

    def wait_for_abort(self):
        self.waitForAbort()
        self.stop()

    def onSettingsChanged(self):  # type: () -> None
        logger.info("settings changed, updating")
        api = self._api
        api.set_user_id(get_user_id())
        api.set_api_server(addon.get_config(CONF_API_SERVER, str))

    def onNotification(self, sender, method, data):  # type: (str, str, str) -> None
        if sender != youtube_api.ADDON_ID:
            return

        try:
            data = youtube_api.parse_notification_payload(data)
        except Exception:
            logger.exception("failed to parse notification payload (%s): %r", method, data)
            return

        logger.debug("notification from YouTube addon: %r %s", method, data)
