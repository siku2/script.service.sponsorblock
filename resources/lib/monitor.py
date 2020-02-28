import json
import logging
import threading

import xbmc
from six.moves.urllib.parse import unquote as url_unquote

from .const import CONF_API_SERVER, CONF_SHOW_SKIPPED_DIALOG, CONF_USER_ID, VAR_PLAYER_PAUSED, VAR_PLAYER_SPEED
from .gui.sponsor_skipped import SponsorSkipped
from .sponsorblock import NotFound, SponsorBlockAPI, SponsorSegment
from .sponsorblock.utils import new_user_id
from .utils import addon

logger = logging.getLogger(__name__)

YOUTUBE_ADDON_ID = "plugin.video.youtube"
PLAYBACK_STARTED = "Other.PlaybackStarted"


def _load_youtube_notification_payload(data):  # type: (str) -> Any
    args = json.loads(data)
    return json.loads(url_unquote(args[0]))


def _sanity_check_segments(segments):  # type: (Iterable[SponsorSegment]) -> bool
    last_start = -1
    for seg in segments:  # type: SponsorSegment
        if seg.end - seg.start <= 0.1:
            logger.debug("%s: invalid start/end time", seg)
            return False

        if seg.start <= last_start:
            logger.debug("%s: wrong order (starts before previous)", seg)
            return False

        last_start = seg.start

    return True


class Monitor(xbmc.Monitor):
    def __init__(self):
        user_id = addon.get_config(CONF_USER_ID, str)
        if not user_id:
            user_id = new_user_id()
            addon.set_config(CONF_USER_ID, user_id)

        logger.debug("using user id: %s", user_id)
        self._api = SponsorBlockAPI(
            user_id=user_id,
            api_server=addon.get_config(CONF_API_SERVER, str),
        )

        self._listener = PlayerMonitor(api=self._api)

    def stop(self):
        self._listener.stop()

    def wait_for_abort(self):
        self.waitForAbort()
        self.stop()

    def on_playback_started(self, video_id):  # type: (str) -> None
        try:
            segments = self._api.get_video_sponsor_times(video_id)
        except NotFound:
            logger.info("video %s has no sponsor segments", video_id)
            return
        except Exception:
            logger.exception("failed to get sponsor times")
            return

        # segments = [
        #     SponsorSegment(uuid=u'96b8915596117a85dfd18add0f27e87f62520dc56f29fd439cca26cb5a7325fd', start=1.988,
        #                    end=9.61),
        #     SponsorSegment(uuid=u'dfea2697b97a8f5179a7524000d3cd969f949a4439f742526b6e25509bf960c3', start=11.44,
        #                    end=15.462)]

        logger.debug("got segments %s", segments)
        assert _sanity_check_segments(segments)
        self._listener.start(segments)

    def onNotification(self, sender, method, data):  # type: (str, str, str) -> None
        if sender != YOUTUBE_ADDON_ID:
            return

        try:
            data = _load_youtube_notification_payload(data)
        except Exception:
            logger.exception("failed to parse notification payload (%s): %r", method, data)
            return

        logger.debug("notification from YouTube addon: %r %s", method, data)
        if method == PLAYBACK_STARTED:
            self.on_playback_started(data["video_id"])
            return


class PlayerMonitor(xbmc.Player):
    def __init__(self, *args, **kwargs):
        self._api = kwargs.pop("api")  # type: SponsorBlockAPI

        super(PlayerMonitor, self).__init__(*args, **kwargs)

        self._segments = []  # List[SponsorSegment]
        self._next_segment = None  # type: Optional[SponsorSegment]
        self._playback_speed = 1.

        self.__wakeup = threading.Condition()
        self.__wakeup_triggered = False
        self._thread = None  # Optional[threading.Thread]
        self._stop = False

    def __t_handle_wakeup(self):
        if xbmc.getCondVisibility(VAR_PLAYER_PAUSED):
            # no next segment when paused
            self._next_segment = None
        else:
            current_time = self.getTime()
            self._next_segment = next((seg for seg in self._segments if seg.start > current_time), None)

        logger.debug("next segment: %s", self._next_segment)

    def __t_skip_sponsor(self):
        seg = self._next_segment
        self.seekTime(seg.end)
        # wait for seek event to trigger
        self._next_segment = None

        if not addon.get_config(CONF_SHOW_SKIPPED_DIALOG, bool):
            return

        def unskip():
            logger.debug("unskipping segment %s", seg)
            self.seekTime(seg.start)

        def report():
            try:
                self._api.vote_sponsor_segment(seg, upvote=False)
            except Exception:
                logger.exception("failed to vote on sponsor segment %s", self)
                addon.show_notification(32005, icon=addon.NOTIFICATION_ERROR)
            else:
                addon.show_notification(32005)

            unskip()

        SponsorSkipped.display(unskip, report)

    def __t_sleep(self):  # type: () -> bool
        seg = self._next_segment
        if seg is None:
            wait_for = None
        else:
            wait_for = seg.start - self.getTime()
            if wait_for <= 0:
                return True

            # adjust for playback speed
            wait_for /= self._playback_speed

        with self.__wakeup:
            self.__wakeup_triggered = False
            logger.debug("sleeping for %s second(s) (or until wakeup)", wait_for)
            self.__wakeup.wait(wait_for)
            return not self.__wakeup_triggered

    def __t_event_loop(self):
        self._playback_speed = float(xbmc.getInfoLabel(VAR_PLAYER_SPEED))
        self._stop = False

        while not self._stop:
            should_cut = self.__t_sleep()
            logger.debug("woke up: should_cut=%s stop=%s", should_cut, self._stop)

            if self._stop:
                break

            if should_cut:
                self.__t_skip_sponsor()
            else:
                self.__t_handle_wakeup()

    def _triger_wakeup(self):
        if not self._thread_running:
            return

        logger.debug("triggering wakeup")
        with self.__wakeup:
            self.__wakeup_triggered = True
            self.__wakeup.notify_all()

    @property
    def _thread_running(self):  # type: () -> bool
        t = self._thread
        return t is not None and t.is_alive()

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
        self._triger_wakeup()

        logger.debug("waiting for listener to join")
        self._thread.join()

        logger.debug("listener stopped")

    def onPlayBackSeek(self, time, offset):  # type: (int, int) -> None
        self._triger_wakeup()

    def onPlayBackEnded(self):  # type: () -> None
        self.stop()

    def onPlayBackPaused(self):  # type: () -> None
        self._triger_wakeup()

    def onPlayBackResumed(self):  # type: () -> None
        self._triger_wakeup()

    def onPlayBackSpeedChanged(self, speed):  # type: (int) -> None
        self._playback_speed = float(speed)
        self._triger_wakeup()
