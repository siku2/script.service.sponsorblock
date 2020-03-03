"""Module for accessing data from the youtube plugin."""

import json
import logging

import xbmcgui
from six.moves.urllib import parse as urlparse

_logger = logging.getLogger(__name__)

ADDON_ID = "plugin.video.youtube"

NOTIFICATION_PLAYBACK_STARTED = "Other.PlaybackStarted"

WINDOW_ID = 10000
PROP_PLAYBACK_JSON = "playback_json"


def parse_notification_payload(data):  # type: (str) -> Any
    args = json.loads(data)
    return json.loads(urlparse.unquote(args[0]))


def get_home_property(key):  # type: (str) -> Any
    return xbmcgui.Window(WINDOW_ID).getProperty("{}-{}".format(ADDON_ID, key))


def get_playback_json():  # type: () -> dict
    """

    The YouTube plugin uses window properties to store data.
    One such property called "playback_json" is used to store data for the current video.
    This function retrieves this property and converts it to a `dict`.

    Warnings:
        The property is read in the `onPlayBackStarted` event and immediately removed.
        This property should only be used in the short time frame starting when the YouTube plugin resolved the video
        and ending when Kodi starts playing it.

        Source: https://github.com/jdf76/plugin.video.youtube/blob/63e35e/resources/lib/youtube_plugin/kodion/utils/player.py#L397

    Returns:
        `dict` containing the playback data
    """
    return json.loads(get_home_property(PROP_PLAYBACK_JSON))


SCHEME_PLUGIN = "plugin"
PATH_PLAY = "/play"


def video_id_from_path(path):  # type: (str) -> Option[str]
    """

    Example path: `plugin://plugin.video.youtube/play/?video_id=SQCfOjhguO0`

    Args:
        path: Complete path of the file.
            Use `Player.FilenameAndPath`

    Returns:
        Video ID that is being played. `None` if the current item isn't a YouTube video.
    """
    try:
        path_url = urlparse.urlsplit(path)
    except Exception:
        return None

    valid_url = path_url.scheme == SCHEME_PLUGIN and \
                path_url.netloc == ADDON_ID and \
                path_url.path.startswith(PATH_PLAY)
    if not valid_url:
        return None

    query = urlparse.parse_qs(path_url.query)
    return query.get("video_id")
