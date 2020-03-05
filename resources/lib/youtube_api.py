"""Module for accessing data from the youtube plugin."""

import json
import logging

import xbmc
import xbmcgui
from six.moves.urllib import parse as urlparse

from .utils import jsonrpc
from .utils.const import VAR_PLAYER_FILE_AND_PATH

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


_IMAGE_SCHEME = "image://"


def get_thumbnail_path():  # type: () -> Optional[str]
    result = jsonrpc.execute("Player.GetItem", 1, ["art"])
    art = result["item"]["art"]  # type: dict
    try:
        thumbnail = art["thumb"]  # type: str
    except KeyError:
        _logger.debug("no thumbnail provided")
        return None

    if not thumbnail.startswith(_IMAGE_SCHEME):
        _logger.warning("expected thumbnail url to start with %r, got %r", _IMAGE_SCHEME, thumbnail)
        return None

    return urlparse.unquote(thumbnail[len(_IMAGE_SCHEME):])


DOMAIN_THUMBNAIL = "ytimg.com"


def video_id_from_thumbnail():
    """
    Example path: `https://i.ytimg.com/vi/SQCfOjhguO0/hqdefault.jpg/`
    """
    thumb_path = get_thumbnail_path()
    if not thumb_path:
        return None

    try:
        thumb_url = urlparse.urlsplit(thumb_path)  # type: urlparse.SplitResult
    except ValueError:
        _logger.exception("thumbnail isn't a URL: %r", thumb_path)
        return None

    if DOMAIN_THUMBNAIL not in thumb_url.hostname:
        return

    parts = thumb_url.path.split("/", 3)
    if len(parts) < 3:
        _logger.warning("thumbnail from ytimg.com with unknown path %r", thumb_url.path)
        return None

    return parts[2]


def get_playing_file_path():  # type: () -> str
    return xbmc.getInfoLabel(VAR_PLAYER_FILE_AND_PATH)


SCHEME_PLUGIN = "plugin"
PATH_PLAY = "/play"

DOMAIN_GOOGLEVIDEO = "googlevideo.com"


def get_video_id():  # type: () -> Option[str]
    """Get the video id for the playing item.

    Example path: `plugin://plugin.video.youtube/play/?video_id=SQCfOjhguO0`

    Returns:
        Video ID that is being played. `None` if the current item isn't a YouTube video.
    """

    try:
        path_url = urlparse.urlsplit(get_playing_file_path())
    except Exception:
        return None

    valid_url = path_url.scheme == SCHEME_PLUGIN and \
                path_url.netloc == ADDON_ID and \
                path_url.path.startswith(PATH_PLAY)
    if not valid_url:
        if path_url.hostname.endswith(DOMAIN_GOOGLEVIDEO):
            _logger.info("playing a video file from googlevideo.com, trying to extract video id from thumbnail")
            return video_id_from_thumbnail()

        return None

    query = urlparse.parse_qs(path_url.query)
    return query.get("video_id")
