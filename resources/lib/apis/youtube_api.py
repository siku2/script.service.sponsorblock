"""Module for accessing data from the YouTube plugin."""

import itertools
import json
import logging

from urllib import parse as urlparse

from .abstract_api import AbstractApi
from .models import NotificationPayload

from ..utils import jsonrpc
from ..utils.xbmc import get_playing_file_path


_logger = logging.getLogger(__name__)


_IMAGE_SCHEME = "image://"
DOMAIN_THUMBNAIL = "ytimg.com"
DOMAIN_GOOGLEVIDEO = "googlevideo.com"
DOMAIN_YOUTUBE = "youtube.com"
DOMAIN_YOUTU_BE = "youtu.be"
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
        video_id = video_id_from_url(get_playing_file_path())
        if video_id:
            return video_id

        # Kodi may replace the original plugin URL with a resolved media URL by
        # the time onPlayBackStarted fires. Player.GetItem can still retain the
        # original URL, so check it before falling back to item metadata.
        item = get_player_item()
        video_id = video_id_from_url(item.get(jsonrpc.LIST_FIELD_FILE, ""))
        if video_id:
            return video_id

        # has_context denotes whether the current video seems to be a youtube video
        # being played outside of the YouTube add-on.
        try:
            hostname = urlparse.urlsplit(get_playing_file_path()).hostname
        except (TypeError, ValueError):
            hostname = None
        has_context = bool(hostname and hostname.endswith(DOMAIN_GOOGLEVIDEO))
        try:
            return video_id_from_list_item(has_context, item=item)
        except Exception:
            _logger.exception("failed to get video id from list item")
            return None

    def should_preload_segments(self, method, data): # type: (str, NotificationPayload) -> bool
        return method == NOTIFICATION_PLAYBACK_INIT


def video_id_from_url(value):
    """Extract a YouTube ID from current and legacy playback URLs."""
    if not value:
        return None

    try:
        parsed = urlparse.urlsplit(value)
        query = urlparse.parse_qs(parsed.query)
    except (TypeError, ValueError):
        return None

    if parsed.scheme == "plugin" and parsed.netloc in (
        "plugin.video.youtube",
        "plugin.video.sendtokodi",
    ):
        video_id = query.get("video_id", query.get("videoid", [None]))[0]
        if video_id:
            return video_id

        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2 and parts[-2] in ("play", "watch"):
            return parts[-1]

    hostname = (parsed.hostname or "").lower()
    if hostname == DOMAIN_YOUTU_BE or hostname.endswith("." + DOMAIN_YOUTU_BE):
        return parsed.path.lstrip("/").split("/", 1)[0] or None
    if hostname == DOMAIN_YOUTUBE or hostname.endswith("." + DOMAIN_YOUTUBE):
        return query.get("v", [None])[0]

    return None


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


def get_player_item():
    try:
        result = jsonrpc.execute(
            "Player.GetItem",
            jsonrpc.PLAYER_VIDEO,
            [
                jsonrpc.LIST_FIELD_ART,
                jsonrpc.LIST_FIELD_FILE,
                jsonrpc.LIST_FIELD_UNIQUEID,
            ],
        )
    except Exception:
        _logger.exception("failed to get item from JSON RPC")
        return {}

    return result.get("item", {})


def video_id_from_list_item(has_context, item=None):  # type: (bool, dict) -> str | None
    if item is None:
        item = get_player_item()

    if not item:
        return None

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
