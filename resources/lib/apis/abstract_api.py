from abc import ABC, abstractmethod
from .models import NotificationPayload


class AbstractApi(ABC):
    """
    Interface for addon specific implementation details.
    """

    @abstractmethod
    def parse_notification_payload(self, data):  # type: (str) -> NotificationPayload | None
        """
        Parse video information from the notification payload of the respective
        app if available. This enables us to do things before the video has
        actually started playing, like preload data based on the video ID.

        May include None fields if the information is unavailable, or return
        None if the notification is not of interest.
        """
        pass

    @abstractmethod
    def get_video_id(self):  # type: () -> str | None
        """
        Get the YouTube video ID of the currently playing video.
        """
        pass

    @abstractmethod
    def should_preload_segments(self, method, data): # type: (str, NotificationPayload) -> bool
        """
        If we should preload skippable segments for the video ID referenced in
        the NotificationPayload.
        """
        pass
