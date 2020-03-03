import logging
import logging
import threading
import time

import xbmc

from . import youtube_api
from .const import CONF_API_SERVER, CONF_SHOW_SKIPPED_DIALOG, CONF_SKIP_COUNT_TRACKING, CONF_USER_ID, VAR_PLAYER_PAUSED, \
    VAR_PLAYER_SPEED
from .gui.sponsor_skipped import SponsorSkipped
from .sponsorblock import NotFound, SponsorBlockAPI, SponsorSegment
from .sponsorblock.utils import new_user_id
from .utils import addon

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
        segments = api.get_video_sponsor_times(video_id)
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


def get_user_id():
    user_id = addon.get_config(CONF_USER_ID, str)
    if not user_id:
        user_id = new_user_id()
        logger.info("generated new user id: %s", user_id)
        addon.set_config(CONF_USER_ID, user_id)

    return user_id


class Monitor(xbmc.Monitor):
    def __init__(self):
        self._api = SponsorBlockAPI(
            user_id=get_user_id(),
            api_server=addon.get_config(CONF_API_SERVER, str),
        )

        self._player_listener = PlayerMonitor(api=self._api)

    def stop(self):
        self._player_listener.stop()

    def wait_for_abort(self):
        self.waitForAbort()
        self.stop()

    def onSettingsChanged(self):  # type: () -> None
        logger.info("settings changed, updating")
        api = self._api
        api.set_user_id(get_user_id())
        api.set_api_server(addon.get_config(CONF_API_SERVER, str))

    def onNotification(self, sender, method, data):  # type: (str, str, str) -> None
        if sender != youtube_api.ADDON_ID:
            return

        try:
            data = youtube_api.parse_notification_payload(data)
        except Exception:
            logger.exception("failed to parse notification payload (%s): %r", method, data)
            return

        logger.debug("notification from YouTube addon: %r %s", method, data)


MAX_UNDERSHOOT = .25
"""Amount of tolerance in seconds for waking up early.

If the listener wakes up and the difference to the target time is bigger than this value, 
it goes back to sleep for the remaining time.
"""
MAX_OVERSHOOT = 1.5
"""Max seconds allowed to move past the start of a sponsor segment before ignoring it."""

MAX_SEEK_AGE = 3
"""Amount of time in seconds after a seek before the seek time expires.

In other words, this is the time after which the Kodi player should start reporting accurate values for 
`Player.getTime()` again.
"""


class PlayerMonitor(xbmc.Player):
    def __init__(self, *args, **kwargs):
        self._api = kwargs.pop("api")  # type: SponsorBlockAPI

        super(PlayerMonitor, self).__init__(*args, **kwargs)

        self._segments = []  # List[SponsorSegment]
        self._next_segment = None  # type: Optional[SponsorSegment]
        self._playback_speed = 1.
        self.__seek = None  # type: Optional[Tuple[float, float]]

        self.__wakeup = threading.Condition()
        self.__wakeup_triggered = False
        self._thread = None  # Optional[threading.Thread]
        self._stop = False

    @property
    def _seek_time(self):  # type: () -> Optional[float]
        try:
            seek_time, timestamp = self.__seek
        except TypeError:
            return None

        age = time.time() - timestamp
        if age > MAX_SEEK_AGE:
            logger.debug("seek time expired")
            self.__seek = None
            return None

        return seek_time + age * self._playback_speed

    @_seek_time.setter
    def _seek_time(self, value):  # type: (float) -> None
        if value is None:
            self.__seek = None
        else:
            self.__seek = (value, time.time())

    def _get_current_time(self):  # type:() -> float
        """Get the current time of the current item.

        This method is the same as `Player.getTime` unless it is called just after seeking.
        For a period after seeking `Player.getTime` still reports the time prior to seeking.
        This is problematic for us because we rely on the current time being correct.
        This function solves this by returning the seek time instead, until the seek time is cleared again.

        Returns:
            Current time in seconds.
        """
        seek_time = self._seek_time
        if seek_time is None:
            return self.getTime()

        return seek_time

    def __select_next_segment(self):  # type: () -> None
        current_time = self._get_current_time()
        logger.debug("searching for next segment after %g", current_time)
        self._next_segment = next((seg for seg in self._segments if seg.start > current_time), None)

    def __t_handle_wakeup(self):
        if xbmc.getCondVisibility(VAR_PLAYER_PAUSED):
            # no next segment when paused
            self._next_segment = None
        else:
            self.__select_next_segment()

        logger.debug("next segment: %s", self._next_segment)

    def __t_skip_sponsor(self):
        seg = self._next_segment
        # let the seek event handle setting the next segment
        self._next_segment = None

        overshoot = self._get_current_time() - seg.start
        if overshoot > MAX_OVERSHOOT:
            logger.warning("overshot segment %s by %s second(s), not skipping", seg, overshoot)
            self.__select_next_segment()
            return

        logger.debug("segment start overshot by %s second(s)", overshoot)
        self.seekTime(seg.end)

        if not addon.get_config(CONF_SHOW_SKIPPED_DIALOG, bool):
            return

        def unskip():
            logger.debug("unskipping segment %s", seg)
            self.seekTime(seg.start)

        def report():
            logger.debug("reporting segment %s", seg)
            try:
                self._api.vote_sponsor_segment(seg, upvote=False)
            except Exception:
                logger.exception("failed to vote on sponsor segment %s", self)
                addon.show_notification(32005, icon=addon.NOTIFICATION_ERROR)
            else:
                addon.show_notification(32005)

            unskip()

        SponsorSkipped.display_async(unskip, report)

        if addon.get_config(CONF_SKIP_COUNT_TRACKING, bool):
            logger.debug("reporting sponsor skipped")
            try:
                self._api.viewed_sponsor_segment(seg)
            except Exception:
                logger.exception("failed to report sponsor skipped")
                # no need for a notification, the user doesn't need to know about this

    def __sleep_until(self, target_time):  # type: (float) -> bool
        logger.debug("waiting until %s (or until wakeup)", target_time)
        while True:
            wait_for = (target_time - self._get_current_time()) / self._playback_speed
            if wait_for <= MAX_UNDERSHOOT:
                return True

            with self.__wakeup:
                logger.debug("sleeping for %s second(s) (or until wakeup)", wait_for)
                self.__wakeup.wait(wait_for)

            if self.__wakeup_triggered:
                return False

    def __t_idle(self):  # type: () -> bool
        if self.__wakeup_triggered:
            logger.debug("entered idle while wakeup has been triggered")
            return False

        seg = self._next_segment
        if seg is not None and self._playback_speed > 0:
            return self.__sleep_until(seg.start)

        logger.debug("sleeping until wakeup triggered")
        with self.__wakeup:
            self.__wakeup.wait()

        return not self.__wakeup_triggered

    def __t_event_loop(self):
        self._playback_speed = float(xbmc.getInfoLabel(VAR_PLAYER_SPEED))

        self._stop = False
        self._seek_time = None
        self.__wakeup_triggered = False

        while not self._stop:
            should_cut = self.__t_idle()
            self.__wakeup_triggered = False
            logger.debug("woke up: should_cut=%s stop=%s", should_cut, self._stop)

            if self._stop:
                break

            if should_cut:
                self.__t_skip_sponsor()
            else:
                self.__t_handle_wakeup()

    @property
    def _thread_running(self):  # type: () -> bool
        t = self._thread
        return t is not None and t.is_alive()

    def _trigger_wakeup(self):
        if not self._thread_running:
            return

        logger.debug("triggering wakeup")
        with self.__wakeup:
            self.__wakeup_triggered = True
            self.__wakeup.notify_all()

    def start(self, segments):  # type: (List[SponsorSegment]) -> None
        assert not self._thread_running
        logger.info("starting background playback listener")

        self._segments = segments
        self._next_segment = segments[0]

        self._thread = threading.Thread(target=self.__t_event_loop, name="Playback Listener")
        self._thread.start()

    def stop(self):
        if not self._thread_running:
            return

        logger.debug("stopping playback listener")
        self._stop = True
        self._trigger_wakeup()

        logger.debug("waiting for listener to join")
        self._thread.join()

        logger.debug("listener stopped")

    def onPlayBackSeek(self, target, offset):  # type: (int, int) -> None
        self._seek_time = target / 1000.
        self._trigger_wakeup()

    def onPlayBackStarted(self):  # type: () -> None
        file_path = xbmc.getInfoLabel("Player.FilenameAndPath")
        video_id = youtube_api.video_id_from_path(file_path)
        if not video_id:
            return

        segments = get_sponsor_segments(self._api, video_id)
        if not segments:
            return

        self.start(segments)

    def onPlayBackEnded(self):  # type: () -> None
        self.stop()

    def onPlayBackPaused(self):  # type: () -> None
        self._seek_time = None
        self._trigger_wakeup()

    def onPlayBackResumed(self):  # type: () -> None
        self._seek_time = None
        self._trigger_wakeup()

    def onPlayBackSpeedChanged(self, speed):  # type: (int) -> None
        self._seek_time = None
        self._playback_speed = float(speed)
        self._trigger_wakeup()
