import logging

import xbmc

from . import youtube_api
from .player_listener import PlayerListener
from .sponsorblock import SponsorBlockAPI
from .sponsorblock.utils import new_user_id
from .utils import addon
from .utils.const import (
    CONF_API_SERVER,
    CONF_CATEGORIES_MAP,
    CONF_CATEGORY_CUSTOM,
    CONF_IGNORE_UNLISTED,
    CONF_USER_ID,
)

logger = logging.getLogger(__name__)


def get_user_id():
    user_id = addon.get_config(CONF_USER_ID, str)
    if not user_id:
        user_id = new_user_id()
        logger.info("generated new user id: %s", user_id)
        addon.set_config(CONF_USER_ID, user_id)

    return user_id


def get_categories():
    categories = set()

    for category, conf_key in CONF_CATEGORIES_MAP.items():
        if addon.get_config(conf_key, bool):
            categories.add(category)

    custom_categories = addon.get_config(CONF_CATEGORY_CUSTOM, str)
    categories.update(
        filter(None, (category.strip() for category in custom_categories.split(",")))
    )
    logger.info("skipping the following categories: %s", categories)
    return list(categories)


class Monitor(xbmc.Monitor):
    def __init__(self):
        self._api = SponsorBlockAPI(
            user_id=get_user_id(),
            api_server=addon.get_config(CONF_API_SERVER, str),
            categories=get_categories(),
        )

        self._player_listener = PlayerListener(api=self._api)

    def stop(self):
        self._player_listener.stop_listener()

    def wait_for_abort(self):
        self.waitForAbort()
        self.stop()

    def onSettingsChanged(self):  # type: () -> None
        logger.info("settings changed, updating")
        api = self._api
        api.set_user_id(get_user_id())
        api.set_api_server(addon.get_config(CONF_API_SERVER, str))
        api.set_categories(get_categories())

    def __handle_playback_init(self, data):
        try:
            video_id = data["video_id"]
        except KeyError:
            logger.warning("received playbackinit notification without video id")
            return

        unlisted = data.get("unlisted", False)
        if unlisted and addon.get_config(CONF_IGNORE_UNLISTED, bool):
            logger.info("ignoring video %s because it's unlisted", video_id)
            self._player_listener.ignore_next_video(video_id)
            return

        # preload the segments
        self._player_listener.preload_segments(video_id)

    def onNotification(self, sender, method, data):  # type: (str, str, str) -> None
        if sender != youtube_api.ADDON_ID:
            return

        try:
            data = youtube_api.parse_notification_payload(data)
        except Exception:
            logger.exception(
                "failed to parse notification payload (%s): %r", method, data
            )
            return

        logger.debug("notification from YouTube addon: %r %s", method, data)
        if method == youtube_api.NOTIFICATION_PLAYBACK_INIT:
            self.__handle_playback_init(data)
