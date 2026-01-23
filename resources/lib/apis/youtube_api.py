"""Module for accessing data from the YouTube plugin."""

import itertools
import json
import logging

from six.moves.urllib import parse as urlparse

from .abstract_api import AbstractApi
from .models import NotificationPayload

from ..utils import jsonrpc
from ..utils.xbmc import get_playing_file_path


_logger = logging.getLogger(__name__)


_IMAGE_SCHEME = "image://"
DOMAIN_THUMBNAIL = "ytimg.com"
DOMAIN_GOOGLEVIDEO = "googlevideo.com"
NOTIFICATION_PLAYBACK_INIT = "Other.PlaybackInit"


_EXPLICIT_UIDS = ("youtubeid", "youtube_id")
"""
unique ids that explicitly identify a youtube video.
"""
_CONTEXT_UIDS = ("videoid", "video_id")
"""
unique ids that require context
"""


class YouTubeApi(AbstractApi):

    def parse_notification_payload(self, data):  # type: (str) -> NotificationPayload | None
        parsed = json.loads(data)
        return NotificationPayload(parsed.get("video_id", None), parsed.get("unlisted", None))

    def get_video_id(self):  # type: () -> str | None
        try:
            path_url = urlparse.urlsplit(get_playing_file_path())
            query = urlparse.parse_qs(path_url.query)
        except Exception:
            return None

        valid_url = (
            path_url.scheme == "plugin"
            and path_url.path.startswith("/play")
        )

        if valid_url:
            return query.get("video_id")[0]

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

    def should_preload_segments(self, method, data): # type: (str, NotificationPayload) -> bool
        return method == NOTIFICATION_PLAYBACK_INIT

def _extract_image_url(img):  # type: (str) -> str
    if not img.startswith(_IMAGE_SCHEME):
        return img

    return urlparse.unquote(img[len(_IMAGE_SCHEME) :])


def _video_id_from_art(art):  # type: (dict) -> str | None
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


def _video_id_from_ids(unique_ids, has_context):  # type: (dict, bool) -> str | None
    if has_context:
        keys = itertools.chain(_EXPLICIT_UIDS, _CONTEXT_UIDS)
    else:
        keys = _EXPLICIT_UIDS

    for key in keys:
        try:
            return unique_ids[key]
        except KeyError:
            pass


def video_id_from_list_item(has_context):  # type: (bool) -> str | None
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
        video_id = _video_id_from_art(art)
        if video_id:
            return video_id

    return None
