import logging
import threading

import xbmc

from . import youtube_api
from .gui.sponsor_skipped import SponsorSkipped
from .sponsorblock import NotFound, SponsorBlockAPI, SponsorSegment
from .utils import addon
from .utils.checkpoint_listener import PlayerCheckpointListener
from .utils.const import (
    CONF_AUTO_UPVOTE,
    CONF_SEGMENT_CHAIN_MARGIN_MS,
    CONF_REDUCE_SKIPS_MS,
    CONF_SHOW_SKIPPED_DIALOG,
    CONF_SKIP_COUNT_TRACKING,
    CONF_VIDEO_END_TIME_MARGIN_MS,
)

logger = logging.getLogger(__name__)


def _sanity_check_segments(segments):  # type: (Iterable[SponsorSegment]) -> bool
    last_start = -1
    for seg in segments:  # type: SponsorSegment
        if seg.end - seg.start <= 0.01:
            logger.error("%s: invalid start/end time", seg)
            return False

        if seg.start <= last_start:
            logger.error("%s: wrong order (starts before previous)", seg)
            return False

        last_start = seg.start

    return True


def get_sponsor_segments(
    api, video_id
):  # type: (SponsorBlockAPI, str) -> Optional[List[SponsorSegment]]
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
    _sanity_check_segments(segments)

    return segments


def vote_on_segment(
    api, seg, upvote, notify_success=True
):  # type: (SponsorBlockAPI, SponsorSegment, bool, bool) -> bool
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

        # set by `onPlaybackStarted` and then read (/ reset) by `onAVStarted`
        self._should_start = False
        self._should_start_lock = threading.Lock()

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
        # Reset existing playback
        self._reset_next_checkpoint()
        self._segments = []
        self._segments_video_id = None

        with self._should_start_lock:
            video_id = youtube_api.get_video_id()
            if not video_id:
                return

            if video_id == self._take_ignore_next_video_id():
                logger.debug("ignoring video %s because it's ignored", video_id)
                return

            if not self._prepare_segments(video_id):
                return

            self._select_next_checkpoint()
            self._should_start = True

    def onAVStarted(self):  # type: () -> None
        with self._should_start_lock:
            if self._should_start:
                self._should_start = False
            else:
                # `onPlayBackStarted` determined that we don't need to start
                return

        self.start_listener()

    def _select_next_checkpoint(self):
        reduce_skips_seconds = (
            addon.get_config(CONF_REDUCE_SKIPS_MS, int) / 1000.0
        )

        current_time = self.getTime()
        logger.debug("searching for next segment after %g", current_time)
        self._next_segment = next(
            (seg for seg in self._segments if self._is_segment_skippable(seg, current_time, reduce_skips_seconds)), None
        )
    
    def _is_segment_skippable(self, seg, current_time, reduce_skips_seconds):
        if seg.start < current_time:
            return False

        chained_end = self.__get_segment_end_handle_overlap(seg)
        min_skip_position = current_time + reduce_skips_seconds 

        if chained_end < min_skip_position:
            logger.debug("skipping segment %s because there is not enough margin for 'Reduce all skips by this much' setting (%g)", seg, reduce_skips_seconds)
            return False

        if chained_end - seg.start < reduce_skips_seconds:
            logger.debug("skipping segment %s because it is shorter than 'Reduce all skips by this much' setting (%g)", seg, reduce_skips_seconds)
            return False

        return True


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

    def __get_segment_end_handle_overlap(self, seg):
        """Get the end time of a segment handling overlap with following segments.

        When another segments starts within the span of the segment but isn't strictly contained in it,
        its end time is used instead.
        This continues until no more overlapping segments are found.
        """
        end_time = seg.end

        try:
            start_index = self._segments.index(seg)
            upcoming_segments = self._segments[start_index:]
        except (IndexError, ValueError):
            return end_time

        segment_chain_margin = (
            addon.get_config(CONF_SEGMENT_CHAIN_MARGIN_MS, int) / 1000.0
        )

        for seg in upcoming_segments:
            # segment start must be bigger than our current `end_time + segment_chain_margin`
            # for us to consider it a separate (non-chain) segment.
            if seg.start > (end_time + segment_chain_margin):
                break
            logger.debug(
                "chaining overlapping segments (possibly with margin setting): %s", seg
            )
            end_time = max(end_time, seg.end)

        return end_time

    def __check_exceeds_video_end(self, time):
        total_time = self.getTotalTime()
        if not total_time:
            logger.warning("couldn't determine total duration of the current video")
            return False

        video_end_time = (
            total_time - addon.get_config(CONF_VIDEO_END_TIME_MARGIN_MS, int) / 1000.0
        )
        return time >= video_end_time

    def __playnext_or_stop(self):
        try:
            playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
            last_item = playlist.getposition() + 1 == playlist.size()
        except Exception:
            logger.exception(
                "failed to determine whether this is the last item in the playlist"
            )
            last_item = False

        if last_item:
            logger.debug("stopping because this is the last item in the playlist")
            self.stop()
        else:
            self.playnext()

    def _reached_checkpoint(self):
        seg = self._next_segment
        seg_target_seek_time = self.__get_segment_end_handle_overlap(seg)

        if self.__check_exceeds_video_end(seg_target_seek_time):
            logger.info("segment ends after end of video, skipping to next video")
            self.__playnext_or_stop()
        else:
            reduce_skips_seconds = (
                addon.get_config(CONF_REDUCE_SKIPS_MS, int) / 1000.0
            )
            self.seekTime(seg_target_seek_time - reduce_skips_seconds)

            # with `playnext` there's no way for the user to "unskip" right now,
            # so we only show the dialog if we're still in the same video.
            if addon.get_config(CONF_SHOW_SKIPPED_DIALOG, bool):
                self.__show_skipped_dialog(seg)

        if addon.get_config(CONF_SKIP_COUNT_TRACKING, bool):
            logger.debug("reporting sponsor skipped")
            try:
                self._api.viewed_sponsor_segment(seg)
            except Exception:
                logger.exception("failed to report sponsor skipped")
                # no need for a notification, the user doesn't need to know about this
