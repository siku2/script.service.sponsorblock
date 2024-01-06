import json

from six.moves.urllib import parse as urlparse

from .abstract_api import AbstractApi
from .models import NotificationPayload

from ..utils.xbmc import get_playing_file_path


class PipedApi(AbstractApi):

    def parse_notification_payload(self, data):  # type: (str) -> NotificationPayload | None
        args = json.loads(data)

        if args[0] != "pushQuery":
            return None

        video_id = args[1][0].get("videoId", None)
        return NotificationPayload(video_id, None)

    def get_video_id(self):  # type: () -> str | None
        try:
            path_url = urlparse.urlsplit(get_playing_file_path())
            query = urlparse.parse_qs(path_url.query)
        except Exception:
            return None

        valid_url = (
            path_url.scheme == "plugin"
            and path_url.path.startswith("/watch/")
        )

        return path_url.path.replace('/watch/', '') if valid_url else None

    def should_preload_segments(self, method, data): # type: (str, NotificationPayload) -> bool
        return data.video_id is not None
