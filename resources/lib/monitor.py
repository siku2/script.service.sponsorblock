import json
import logging
import threading

import xbmc
from six.moves.urllib.parse import unquote as url_unquote

from .const import VAR_PLAYER_PAUSED, VAR_PLAYER_SPEED
from .sponsorblock import NotFound, SponsorBlockAPI
from .sponsorblock.models import SponsorSegment

logger = logging.getLogger(__name__)

YOUTUBE_ADDON_ID = "plugin.video.youtube"
PLAYBACK_STARTED = "Other.PlaybackStarted"


def _load_youtube_notification_payload(data):  # type: (str) -> Any
    args = json.loads(data)
    return json.loads(url_unquote(args[0]))


class Monitor(xbmc.Monitor):
    def __init__(self):
        # FIXME settings don't work
        # self._api = SponsorBlockAPI(
        #     user_id=addon.get_config(CONF_USER_ID, str),
        #     api_server=addon.get_config(CONF_API_SERVER, str),
        # )
        self._api = SponsorBlockAPI(
            user_id="",
            api_server="",
        )

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
        player = xbmc.Player()

        listener = PlayerMonitor()
        listener.init(segments)
        listener.start()

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
    # FIXME use __init__ and find out why it doesn't work
    def init(self, segments):
        self._segments = segments
        self._next_segment = segments[0]  # type: SponsorSegment
        self._playback_speed = 1.

        self.__wakeup = threading.Condition()
        self.__wakeup_triggered = False
        self._thread = threading.Thread(target=self.__t_event_loop, name="Playback Listener")
        self._stop = False

    def __t_handle_wakeup(self):
        if xbmc.getCondVisibility(VAR_PLAYER_PAUSED):
            # no next segment when paused
            self._next_segment = None
        else:
            current_time = self.getTime()
            self._next_segment = next((seg for seg in self._segments if seg.start > current_time), None)

        logger.debug("next segment: %s", self._next_segment)

    def __t_sleep(self):
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

        while not self._stop:
            should_cut = self.__t_sleep()
            logger.debug("woke up: should_cut=%s stop=%s", should_cut, self._stop)

            if self._stop:
                break

            if should_cut:
                self.seekTime(self._next_segment.end)
                # wait for seek event
                self._next_segment = None
            else:
                self.__t_handle_wakeup()

    def __triger_wakeup(self):
        logger.debug("triggering wakeup")
        with self.__wakeup:
            self.__wakeup_triggered = True
            self.__wakeup.notify_all()

    def start(self):
        assert not self._thread.is_alive()

        logger.info("starting background playback listener")
        self._thread.start()

    def stop(self):
        logger.debug("stopping playback listener")
        self._stop = True
        self.__triger_wakeup()
        if self._thread.is_alive():
            self._thread.join()

    def onPlayBackSeek(self, time, offset):  # type: (int, int) -> None
        self.__triger_wakeup()

    def onPlayBackEnded(self):  # type: () -> None
        self.stop()

    def onPlayBackPaused(self):  # type: () -> None
        self.__triger_wakeup()

    def onPlayBackResumed(self):  # type: () -> None
        self.__triger_wakeup()

    def onPlayBackSpeedChanged(self, speed):  # type: (int) -> None
        self._playback_speed = float(speed)
        self.__triger_wakeup()
