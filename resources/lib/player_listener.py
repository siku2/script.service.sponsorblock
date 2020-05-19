import logging
import threading

from . import youtube_api
from .gui.sponsor_skipped import SponsorSkipped
from .sponsorblock import NotFound, SponsorBlockAPI, SponsorSegment
from .utils import addon
from .utils.checkpoint_listener import PlayerCheckpointListener
from .utils.const import CONF_AUTO_UPVOTE, CONF_SHOW_SKIPPED_DIALOG, CONF_SKIP_COUNT_TRACKING

logger = logging.getLogger(__name__)


def _sanity_check_segments(segments):  # type: (Iterable[SponsorSegment]) -> bool
    last_start = -1
    for seg in segments:  # type: SponsorSegment
        if seg.end - seg.start <= 0.1:
            logger.error("%s: invalid start/end time", seg)
            return False

        if seg.start <= last_start:
            logger.error("%s: wrong order (starts before previous)", seg)
            return False

        last_start = seg.start

    return True


def get_sponsor_segments(api, video_id):  # type: (SponsorBlockAPI, str) -> Optional[List[SponsorSegment]]
    try:
        segments = api.get_skip_segments(video_id)
    except NotFound:
        logger.info("video %s has no sponsor segments", video_id)
        return None
    except Exception:
        logger.exception("failed to get sponsor times")
        return None

    if not segments:
        logger.warning("received empty list of sponsor segments for video %s", video_id)
        return None

    logger.debug("got segments %s", segments)
    assert _sanity_check_segments(segments)
    return segments


def vote_on_segment(api, seg, upvote,
                    notify_success=True):  # type: (SponsorBlockAPI, SponsorSegment, bool, bool) -> bool
    try:
        api.vote_sponsor_segment(seg, upvote=upvote)
    except Exception:
        logger.exception("failed to vote on sponsor segment %s", seg)
        addon.show_notification(32004, icon=addon.NOTIFICATION_ERROR)
    else:
        if notify_success:
            addon.show_notification(32005)


class PlayerListener(PlayerCheckpointListener):
    def __init__(self, *args, **kwargs):
        self._api = kwargs.pop("api")  # type: SponsorBlockAPI

        super(PlayerListener, self).__init__(*args, **kwargs)

        self._load_segment_lock = threading.Lock()
        self._ignore_next_video_id = None
        self._segments_video_id = None
        self._segments = []  # List[SponsorSegment]
        self._next_segment = None  # type: Optional[SponsorSegment]

    def preload_segments(self, video_id):
        assert not self._thread_running

        if self._load_segment_lock.locked():
            # try to avoid waiting for the lock
            return

        logger.debug("preloading segments for video %s", video_id)
        self._prepare_segments(video_id)

    def ignore_next_video(self, video_id):
        assert not self._thread_running
        self._ignore_next_video_id = video_id

    def _take_ignore_next_video_id(self):
        v = self._ignore_next_video_id
        self._ignore_next_video_id = None
        return v

    def _prepare_segments(self, video_id):
        with self._load_segment_lock:
            if video_id != self._segments_video_id:
                self._segments_video_id = video_id
                self._segments = get_sponsor_segments(self._api, video_id)
            else:
                logger.info("segments for video %s already loaded", video_id)

        return bool(self._segments)

    def onPlayBackStarted(self):  # type: () -> None
        video_id = youtube_api.get_video_id()
        if not video_id:
            return

        if video_id == self._take_ignore_next_video_id():
            logger.debug("ignoring video %s because it's ignored", video_id)
            return

        if not self._prepare_segments(video_id):
            return

        self._next_segment = self._segments[0]
        self.start()

    def _select_next_checkpoint(self):
        current_time = self._get_current_time()
        logger.debug("searching for next segment after %g", current_time)
        self._next_segment = next((seg for seg in self._segments if seg.start > current_time), None)

    def _reset_next_checkpoint(self):
        self._next_segment = None

    def _get_checkpoint(self):
        seg = self._next_segment
        return seg.start if seg is not None else None

    def __show_skipped_dialog(self, seg):
        def unskip():
            logger.debug("unskipping segment %s", seg)
            self.seekTime(seg.start)

        def report():
            logger.debug("reporting segment %s", seg)
            vote_on_segment(self._api, seg, upvote=False)

            unskip()

        def on_expire():
            if not addon.get_config(CONF_AUTO_UPVOTE, bool):
                return

            logger.debug("automatically upvoting %s", seg)
            vote_on_segment(self._api, seg, upvote=True, notify_success=False)

        SponsorSkipped.display_async(unskip, report, on_expire)

    def _reached_checkpoint(self):
        seg = self._next_segment
        # TODO handle seg.end being beyond end of video!
        self.seekTime(seg.end)

        if addon.get_config(CONF_SHOW_SKIPPED_DIALOG, bool):
            self.__show_skipped_dialog(seg)

        if addon.get_config(CONF_SKIP_COUNT_TRACKING, bool):
            logger.debug("reporting sponsor skipped")
            try:
                self._api.viewed_sponsor_segment(seg)
            except Exception:
                logger.exception("failed to report sponsor skipped")
                # no need for a notification, the user doesn't need to know about this
