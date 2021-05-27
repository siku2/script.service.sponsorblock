"""Module for accessing data from the youtube plugin."""

import itertools
import json
import logging

import xbmc
from six.moves.urllib import parse as urlparse

from .utils import jsonrpc
from .utils.const import VAR_PLAYER_FILE_AND_PATH

_logger = logging.getLogger(__name__)

ADDON_ID = "plugin.video.youtube"

NOTIFICATION_PLAYBACK_INIT = "Other.PlaybackInit"


def parse_notification_payload(data):  # type: (str) -> Any
    args = json.loads(data)
    return json.loads(urlparse.unquote(args[0]))


_IMAGE_SCHEME = "image://"


def _extract_image_url(img):  # type: (str) -> str
    if not img.startswith(_IMAGE_SCHEME):
        return img

    return urlparse.unquote(img[len(_IMAGE_SCHEME) :])


DOMAIN_THUMBNAIL = "ytimg.com"


def _video_id_from_art(art, has_context):  # type: (dict, bool) -> Optional[str]
    """
    Example path: `https://i.ytimg.com/vi/SQCfOjhguO0/hqdefault.jpg/`
    """
    try:
        thumb = art["thumb"]  # type: str
    except KeyError:
        return None
    else:
        thumb_path = _extract_image_url(thumb)

    try:
        thumb_url = urlparse.urlsplit(thumb_path)  # type: urlparse.SplitResult
    except ValueError:
        _logger.debug("thumbnail isn't a URL: %r", thumb_path)
        return None

    if thumb_url.hostname is None or DOMAIN_THUMBNAIL not in thumb_url.hostname:
        return

    parts = thumb_url.path.split("/", 3)
    if len(parts) < 3:
        _logger.warning("thumbnail from ytimg.com with invalid path %r", thumb_url.path)
        return None

    return parts[2]


# unique ids that explicitly identify a youtube video.
_EXPLICIT_UIDS = ("youtubeid", "youtube_id")
# unique ids that require context
_CONTEXT_UIDS = ("videoid", "video_id")


def _video_id_from_ids(unique_ids, has_context):  # type: (dict, bool) -> Optional[str]
    if has_context:
        keys = itertools.chain(_EXPLICIT_UIDS, _CONTEXT_UIDS)
    else:
        keys = _EXPLICIT_UIDS

    for key in keys:
        try:
            return unique_ids[key]
        except KeyError:
            pass


def video_id_from_list_item(has_context):  # type: (bool) -> Optional[str]
    try:
        result = jsonrpc.execute(
            "Player.GetItem",
            jsonrpc.PLAYER_VIDEO,
            [
                jsonrpc.LIST_FIELD_ART,
                jsonrpc.LIST_FIELD_UNIQUEID,
            ],
        )
    except Exception:
        _logger.exception("failed to get item from JSON RPC")
        return None

    item = result["item"]  # type: dict

    # extract from unique ids

    try:
        unique_ids = item[jsonrpc.LIST_FIELD_UNIQUEID]
    except KeyError:
        pass
    else:
        video_id = _video_id_from_ids(unique_ids, has_context)
        if video_id:
            return video_id

    # extract from art

    try:
        art = item[jsonrpc.LIST_FIELD_ART]
    except KeyError:
        pass
    else:
        video_id = _video_id_from_art(art, has_context)
        if video_id:
            return video_id

    return None


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

    valid_url = (
        path_url.scheme == SCHEME_PLUGIN
        and path_url.netloc == ADDON_ID
        and path_url.path.startswith(PATH_PLAY)
    )
    if valid_url:
        query = urlparse.parse_qs(path_url.query)
        return query.get("video_id")

    # has_context denotes whether the current video seems to be a youtube video
    # being played outside of the YouTube add-on.
    if path_url.hostname is None:
        has_context = False
    else:
        has_context = path_url.hostname.endswith(DOMAIN_GOOGLEVIDEO)
    try:
        return video_id_from_list_item(has_context)
    except Exception:
        _logger.exception("failed to get video id from list item")
        return None
